@echo off
:: Batch file to run Streamlit PDF/Image Compressor App

echo ==========================================
echo  🚀 Starting Streamlit App (Image & PDF Compressor)
echo ==========================================

:: Step 1: Check if virtual environment exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

:: Step 2: Activate virtual environment
call venv\Scripts\activate

:: Step 3: Install requirements
echo Installing required libraries...
pip install --upgrade pip
pip install streamlit pillow pymupdf

:: Step 4: Run the Streamlit app
echo Launching Streamlit App...
streamlit run app.py

pause
