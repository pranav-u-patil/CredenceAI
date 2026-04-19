@echo off
echo.
echo ╔══════════════════════════════════════════════╗
echo ║       NewsIntel — Intelligence Platform      ║
echo ╚══════════════════════════════════════════════╝
echo.

cd backend
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
echo Installing Python dependencies...
pip install -q -r requirements.txt
python -c "import textblob; textblob.download_corpora(quiet=True)" 2>nul

echo Starting backend on port 8000...
start "NewsIntel Backend" uvicorn main:app --host 0.0.0.0 --port 8000 --reload

timeout /t 3 /nobreak >nul

cd ..\frontend
if not exist node_modules (
    echo Installing Node dependencies...
    npm install
)

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   Open: http://localhost:3000
echo   API:  http://localhost:8000/docs
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

npm start
