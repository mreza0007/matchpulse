@echo off
setlocal

cd /d "%~dp0backend\frontend"

npm run dev

if errorlevel 1 (
    echo.
    echo Frontend stopped with an error.
    pause
)