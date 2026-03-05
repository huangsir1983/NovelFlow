@echo off
echo ========================================
echo   NovelFlow Dev Server Start
echo ========================================
echo.

REM Ensure Node.js and npm global bin are in PATH
set "PATH=D:\nodejs;%APPDATA%\npm;C:\Windows\System32;%PATH%"

echo [1/2] Starting Backend (FastAPI)...
start "NovelFlow Backend" cmd /k "set PATH=C:\Windows\System32;%PATH% && cd /d %~dp0..\backend && call .venv\Scripts\activate.bat && python -m uvicorn main:app --reload --port 8000"

ping -n 3 127.0.0.1 > nul

echo [2/2] Starting Frontend (Next.js)...
start "NovelFlow Frontend" cmd /k "set PATH=D:\nodejs;%APPDATA%\npm;C:\Windows\System32;%PATH% && cd /d %~dp0.. && pnpm dev:web"

echo.
echo Both servers starting...
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo.
pause
