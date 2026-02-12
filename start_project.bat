@echo off
cd /d "%~dp0"

echo ===================================================
echo   Intelligent Question Generation System Launcher
echo ===================================================
echo.

:: 1. Check Python
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 goto InstallPython
echo     - Python found.
goto CheckNode

:InstallPython
echo     - Python not found. Attempting to install via winget...
winget install -e --id Python.Python.3.11
if errorlevel 1 (
    echo [ERROR] Failed to install Python automatically.
    echo Please install Python 3.10+ manually from https://www.python.org/
    pause
    exit /b 1
)
echo     - Python installed. Please restart script.
pause
exit /b 0

:CheckNode
echo.
echo [2/5] Checking Node.js...
call npm --version >nul 2>&1
if errorlevel 1 goto InstallNode
echo     - Node.js found.
goto SetupBackend

:InstallNode
echo     - Node.js not found. Attempting to install via winget...
winget install -e --id OpenJS.NodeJS.LTS
if errorlevel 1 (
    echo [ERROR] Failed to install Node.js automatically.
    echo Please install Node.js manually from https://nodejs.org/
    pause
    exit /b 1
)
echo     - Node.js installed. Please restart script.
pause
exit /b 0

:SetupBackend
echo.
echo [3/5] Setting up Backend...
if not exist "backend" (
    echo [ERROR] 'backend' folder not found!
    pause
    exit /b 1
)
cd "backend"

if exist "venv" goto ActivateVenv
echo     - Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create venv.
    echo Please make sure Python is installed correctly.
    pause
    exit /b 1
)

:ActivateVenv
echo     - Activating venv...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate venv.
    pause
    exit /b 1
)

if not exist "requirements.txt" goto StartBackend
echo     - Installing backend dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install backend dependencies.
    pause
    exit /b 1
)

:StartBackend
echo     - Starting Backend Server...
start "Backend Server" cmd /k "title Backend Server && venv\Scripts\activate.bat && python run.py"
cd ..

:SetupFrontend
echo.
echo [4/5] Setting up Frontend...
if not exist "frontend" (
    echo [ERROR] 'frontend' folder not found!
    pause
    exit /b 1
)
cd "frontend"

if exist "node_modules" goto StartFrontend
echo     - Installing frontend dependencies...
call npm install
if errorlevel 1 (
    echo [ERROR] Failed to install frontend dependencies.
    pause
    exit /b 1
)

:StartFrontend
echo     - Starting Frontend Server...
start "Frontend Server" cmd /k "title Frontend Server && npm run dev"
cd ..

:OpenBrowser
echo.
echo [5/5] Launching...
echo Waiting 1 seconds for services to initialize...
timeout /t 1 >nul
start http://localhost:5173

echo.
echo [SUCCESS] System started!
echo Backend API: http://localhost:5000
echo Frontend UI: http://localhost:5173
echo.
echo Keep this window open or minimize it.
pause
