@echo off
setlocal
title Build Sovereign Workstation
echo ==========================================
echo   Sovereign Workstation - EXE Builder
echo ==========================================
echo.
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11+ from https://www.python.org/downloads/windows/
  echo During installation, enable "Add Python to PATH".
  pause
  exit /b 1
)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Could not install runtime dependencies. Check the output above.
  pause
  exit /b 1
)
python -m pip install pyinstaller
if errorlevel 1 (
  echo Could not install PyInstaller. Check your internet connection and try again.
  pause
  exit /b 1
)
python -m PyInstaller --noconfirm --clean --onefile --windowed --name SovereignWorkstation main.py
if errorlevel 1 (
  echo EXE build failed. Read the error above.
  pause
  exit /b 1
)
echo.
echo Build complete! Your EXE is here:
echo %CD%\dist\SovereignWorkstation.exe
pause
