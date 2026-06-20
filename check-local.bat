@echo off
setlocal

cd /d "%~dp0"

echo.
echo === Git status ===
git status

echo.
echo === Testing backend on http://127.0.0.1:8000 ===
curl "http://127.0.0.1:8000/matches?status=upcoming"

echo.
echo.
echo === Testing frontend proxy on http://127.0.0.1:5173 ===
curl "http://127.0.0.1:5173/api/matches?status=upcoming"

echo.
echo.
echo Local checks finished.
pause