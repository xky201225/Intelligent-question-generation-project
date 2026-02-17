@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ===================================================
echo   Intelligent Question Generation System Launcher
echo ===================================================
echo.

:: Check for Admin privileges (optional but helpful for installers)
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] Running with Admin privileges.
) else (
    echo [INFO] Running as User. Popups may appear for installation.
)

:: ---------------------------------------------------
:: 1. Check Python
:: ---------------------------------------------------
echo [1/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo     - Python found.
    goto CheckNode
)

echo     - Python not found.
echo     - Attempting to install Python automatically...

:: Try Winget first (Preferred)
winget --version >nul 2>&1
if %errorlevel% equ 0 (
    echo     - Winget found. Installing Python...
    winget install -e --id Python.Python.3.11 --scope machine
    if %errorlevel% equ 0 goto PythonInstalled
)

:: Fallback to PowerShell download
echo     - Winget not found or failed. Downloading Python installer via PowerShell...
set "PYTHON_URL=https://www.python.org/ftp/python/3.11.5/python-3.11.5-amd64.exe"
set "PYTHON_EXE=python_installer.exe"

powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_EXE%'"

if exist "%PYTHON_EXE%" (
    echo     - Running Python installer...
    echo     - [IMPORTANT] A window will appear. Please wait for it to finish.
    
    :: Use passive mode to show progress bar but automate clicks
    start /wait "" "%PYTHON_EXE%" /passive InstallAllUsers=1 PrependPath=1 Include_test=0
    
    if %errorlevel% neq 0 (
        echo     - Passive install failed. Switching to interactive mode...
        echo     - Please manually check "Add Python to PATH" and click "Install Now".
        start /wait "" "%PYTHON_EXE%"
    )
    del "%PYTHON_EXE%"
) else (
    echo [ERROR] Failed to download Python installer.
    goto InstallPythonFail
)

:PythonInstalled
:: Verify installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] Python command not found immediately.
    echo [WARN] You may need to restart this script or your computer.
    echo [WARN] Trying to refresh environment variables...
    call RefreshEnv.cmd >nul 2>&1
)

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python still not detected. Please restart the script manually.
    pause
    exit /b 1
)

:CheckNode
:: ---------------------------------------------------
:: 2. Check Node.js
:: ---------------------------------------------------
echo.
echo [2/5] Checking Node.js...
call npm --version >nul 2>&1
if %errorlevel% equ 0 (
    echo     - Node.js found.
    goto SetupBackend
)

echo     - Node.js not found.
echo     - Attempting to install Node.js automatically...

:: Try Winget
winget --version >nul 2>&1
if %errorlevel% equ 0 (
    echo     - Winget found. Installing Node.js...
    winget install -e --id OpenJS.NodeJS.LTS
    if %errorlevel% equ 0 goto NodeInstalled
)

:: Fallback to PowerShell download
echo     - Winget not found. Downloading Node.js installer...
set "NODE_URL=https://nodejs.org/dist/v18.17.1/node-v18.17.1-x64.msi"
set "NODE_MSI=node_installer.msi"

powershell -Command "Invoke-WebRequest -Uri '%NODE_URL%' -OutFile '%NODE_MSI%'"

if exist "%NODE_MSI%" (
    echo     - Running Node.js installer...
    echo     - Please follow the installation steps in the popup window.
    start /wait msiexec /i "%NODE_MSI%" /passive
    del "%NODE_MSI%"
) else (
    echo [ERROR] Failed to download Node.js installer.
    goto InstallNodeFail
)

:NodeInstalled
echo     - Node.js installed.
call npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] npm command not found. Please restart the script.
    pause
    exit /b 1
)

:SetupBackend
:: ---------------------------------------------------
:: 3. Setup Backend
:: ---------------------------------------------------
echo.
echo [3/5] Setting up Backend...
if not exist "backend" (
    echo [ERROR] 'backend' folder not found!
    pause
    exit /b 1
)
cd "backend"

:: Create venv
if not exist "venv" (
    echo     - Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create venv. Check Python installation.
        pause
        exit /b 1
    )
)

:: Install dependencies
if exist "requirements.txt" (
    echo     - Installing backend dependencies...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [WARN] pip install returned errors. Continuing anyway...
    )
    call venv\Scripts\deactivate.bat
)

:: Start Backend
echo     - Starting Backend Server...
start "Backend Server" cmd /k "title Backend Server && venv\Scripts\activate.bat && python run.py"
cd ..

:SetupFrontend
:: ---------------------------------------------------
:: 4. Setup Frontend
:: ---------------------------------------------------
echo.
echo [4/5] Setting up Frontend...
if not exist "frontend" (
    echo [ERROR] 'frontend' folder not found!
    pause
    exit /b 1
)
cd "frontend"

echo     - Installing frontend dependencies (using npmmirror for better connectivity)...
call npm install --registry=https://registry.npmmirror.com
if %errorlevel% neq 0 (
    echo [ERROR] npm install failed.
    echo [TIP] Try running "npm install" manually in the frontend directory.
    pause
    exit /b 1
)

:: Start Frontend
echo     - Starting Frontend Server...
start "Frontend Server" cmd /k "title Frontend Server && npm run dev"
cd ..

:OpenBrowser
:: ---------------------------------------------------
:: 5. Launch Browser
:: ---------------------------------------------------
echo.
echo [5/5] Launching...
echo Waiting 5 seconds for services to initialize...
timeout /t 5 >nul
start http://localhost:5173

echo.
echo [SUCCESS] System started!
echo Backend API: http://localhost:5000
echo Frontend UI: http://localhost:5173
echo.
echo You can close this window, but keep the Backend/Frontend windows open.
pause
exit /b 0

:InstallPythonFail
echo [ERROR] Could not install Python.
echo Please install Python 3.10+ manually from https://www.python.org/
pause
exit /b 1

:InstallNodeFail
echo [ERROR] Could not install Node.js.
echo Please install Node.js manually from https://nodejs.org/
pause
exit /b 1
