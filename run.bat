@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
)
".venv\Scripts\python.exe" -c "import pynput" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Install Python 3.11 or newer from python.org and check Add python.exe to PATH.
    pause
    exit /b 1
  )
)
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" main.py
) else (
  start "" ".venv\Scripts\python.exe" main.py
)
