@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python main.py
