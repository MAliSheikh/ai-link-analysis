@echo off
setlocal
cd /d "%~dp0"

if not exist ".env" (
    echo Missing .env file.
    echo Copy .env.example to .env, add your Gemini API key, and run start.bat again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create the virtual environment.
        echo Install Python 3.10 or newer and ensure "python" is available in PATH.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import fastapi, uvicorn, pydantic, httpx, bs4, dotenv, playwright" >nul 2>&1
if errorlevel 1 (
    echo Installing project dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Dependency installation failed.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo Failed to install the Chromium browser required for JavaScript-rendered websites.
    pause
    exit /b 1
)

echo Running tests before startup...
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 (
    echo Tests failed. Fix the test failures before starting the API.
    pause
    exit /b 1
)

echo.
echo Starting the API at http://localhost:4000
echo Swagger documentation: http://localhost:4000/docs
echo Press Ctrl+C to stop the server.
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 4000
