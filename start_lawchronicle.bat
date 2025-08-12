@echo off
echo ========================================
echo    Starting LawChronicle Application
echo ========================================
echo.

echo Starting Backend Server...
cd /d "%~dp0backend"
start "LawChronicle Backend" cmd /k "python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

echo Waiting 3 seconds for backend to start...
timeout /t 3 /nobreak > nul

echo Starting Frontend Server...
cd /d "%~dp0frontend"
start "LawChronicle Frontend" cmd /k "npm start"

echo.
echo ========================================
echo    LawChronicle Application Started!
echo ========================================
echo.
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://localhost:3000
echo API Docs: http://127.0.0.1:8000/docs
echo.
echo To stop both servers, run: stop_lawchronicle.bat
echo Or close the terminal windows manually
echo.
pause
