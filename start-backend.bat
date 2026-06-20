@echo off
setlocal

cd /d "%~dp0backend"
call venv\Scripts\activate

uvicorn main:api --port 8000

if errorlevel 1 (
    echo.
    echo Backend stopped with an error.
    pause
)