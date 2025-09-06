import streamlit as st
from PIL import Image
import fitz  # PyMuPDF
from io import BytesIO
import zipfile

# -----------------------------
# Config
# -----------------------------
TARGET_MB = 2.0  # target file size in MB
st.set_page_config(page_title="Universal Image & PDF Compressor", page_icon="📦", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T']:
        if abs(num) < 1024.0:
            return f"{num:3.2f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.2f}PB"

def bytes_to_mb(b):
    return b / (1024 * 1024)

def compress_image_bytes(file_bytes: bytes, target_mb: float = TARGET_MB, min_quality=20, min_scale=0.2):
    orig_size = len(file_bytes)
    try:
        img = Image.open(BytesIO(file_bytes)).convert("RGB")
    except Exception:
        return file_bytes, False

    width, height = img.size
    best_bytes = file_bytes
    best_size = orig_size

    scales = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, min_scale]
    for scale in scales:
        new_w = max(1, int(width * scale))
        new_h = max(1, int(height * scale))
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        for q in range(95, min_quality - 1, -5):
            buf = BytesIO()
            try:
                resized.save(buf, format="JPEG", quality=q, optimize=True)
            except Exception:
                resized.save(buf, format="JPEG", quality=q)
            data = buf.getvalue()
            if len(data) < best_size:
                best_size = len(data)
                best_bytes = data
            if bytes_to_mb(len(data)) <= target_mb:
                if len(data) <= orig_size:
                    return data, True
                else:
                    break
    if best_size < orig_size:
        return best_bytes, True
    return file_bytes, False

def compress_pdf_bytes(file_bytes: bytes, target_mb: float = TARGET_MB, start_dpi=150):
    orig_size = len(file_bytes)
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception:
        return file_bytes, False

    images = []
    for p in range(len(doc)):
        page = doc.load_page(p)
        dpi = start_dpi
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)

    compressed_pages = []
    for img in images:
        buf = BytesIO()
        try:
            img.save(buf, format="JPEG", quality=85, optimize=True)
        except Exception:
            img.save(buf, format="JPEG", quality=85)
        data = buf.getvalue()
        compressed_pages.append(data)

    if not compressed_pages:
        return file_bytes, False

    try:
        pil_images = [Image.open(BytesIO(b)).convert("RGB") for b in compressed_pages]
        out = BytesIO()
        pil_images[0].save(out, format="PDF", save_all=True, append_images=pil_images[1:])
        result = out.getvalue()
    except Exception:
        return file_bytes, False

    if len(result) < orig_size:
        return result, True
    return file_bytes, False

# -----------------------------
# Session state
# -----------------------------
if "files" not in st.session_state:
    st.session_state["files"] = []
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0  # reset key for uploader

st.title("📦 Image & PDF Compressor")

# File uploader with reset key
uploaded = st.file_uploader(
    "Upload files (multiple allowed)",
    accept_multiple_files=True,
    type=["png", "jpg", "jpeg", "webp", "bmp", "pdf"],
    key=st.session_state["uploader_key"]
)

if uploaded:
    for f in uploaded:
        b = f.read()
        key = (f.name, len(b))
        exists = any((x["name"], x["size"]) == key for x in st.session_state["files"])
        if not exists:
            st.session_state["files"].append({
                "name": f.name,
                "bytes": b,
                "type": "pdf" if f.name.lower().endswith('.pdf') else "image",
                "size": len(b),
                "compressed_bytes": None,
                "changed": False,
            })

# Show uploaded files
st.markdown("### Uploaded files")
if not st.session_state["files"]:
    st.info("No files uploaded yet.")
else:
    cols = st.columns([0.55, 0.15, 0.15, 0.15])
    cols[0].markdown("**File name**")
    cols[1].markdown("**Original size**")
    cols[2].markdown("**Compressed size**")
    cols[3].markdown("**Actions**")

    to_remove = []
    for idx, item in enumerate(st.session_state["files"]):
        c0, c1, c2, c3 = st.columns([0.55, 0.15, 0.15, 0.15])
        c0.write(item["name"])
        c1.write(sizeof_fmt(item["size"]))
        if item["compressed_bytes"]:
            c2.success(sizeof_fmt(len(item["compressed_bytes"])))
            # Replace "Compress" with "Download"
            c3.download_button("Download", data=item["compressed_bytes"],
                               file_name=item["name"], key=f"dl_after_compress_{idx}")
        else:
            c2.write("-")
            if c3.button("Compress", key=f"compress_{idx}"):
                with st.spinner(f"Compressing {item['name']}..."):
                    try:
                        if item["type"] == "image":
                            res, changed = compress_image_bytes(item["bytes"])
                        else:
                            res, changed = compress_pdf_bytes(item["bytes"])
                    except Exception:
                        res, changed = item["bytes"], False
                    if res and len(res) < item["size"]:
                        item["compressed_bytes"] = res
                        item["changed"] = True
                        st.success(f"{item['name']} compressed: {sizeof_fmt(len(res))}")
                    else:
                        item["compressed_bytes"] = item["bytes"]
                        item["changed"] = False
                        st.warning(f"Compression did not reduce size for {item['name']}.")
                    st.rerun()

        if c3.button("Remove", key=f"remove_{idx}"):
            to_remove.append(idx)

    if to_remove:
        for i in sorted(to_remove, reverse=True):
            st.session_state["files"].pop(i)
        st.rerun()

# Global controls
st.markdown("---")
col1, col2, col3 = st.columns([0.3, 0.3, 0.4])
with col1:
    if st.button("Compress All"):
        files = st.session_state["files"]
        if not files:
            st.warning("No files to compress.")
        else:
            for i, item in enumerate(files):
                try:
                    if item["type"] == "image":
                        res, changed = compress_image_bytes(item["bytes"])
                    else:
                        res, changed = compress_pdf_bytes(item["bytes"])
                except Exception:
                    res, changed = item["bytes"], False
                if res and len(res) < item["size"]:
                    item["compressed_bytes"] = res
                    item["changed"] = True
                else:
                    item["compressed_bytes"] = item["bytes"]
                    item["changed"] = False
            st.success("All files processed. Check compressed sizes above.")

with col2:
    if st.button("Download All Compressed (ZIP)"):
        files = st.session_state["files"]
        if not files:
            st.warning("No files available to download.")
        else:
            zip_buf = BytesIO()
            with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
                for item in files:
                    data = item["compressed_bytes"] if item.get("compressed_bytes") else item["bytes"]
                    z.writestr(item["name"], data)
            zip_buf.seek(0)
            st.download_button("Download ZIP", data=zip_buf, file_name="compressed_files.zip")

with col3:
    if st.button("Clear All"):
        st.session_state["files"].clear()
        st.session_state["uploader_key"] += 1  # reset uploader widget
        st.rerun()
