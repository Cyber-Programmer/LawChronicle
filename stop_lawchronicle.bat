@echo off
echo ========================================
echo   Stopping LawChronicle Application
echo ========================================
echo.

echo Stopping Backend Server (Python/Uvicorn)...
taskkill /f /im python.exe 2>nul
if %errorlevel% == 0 (
    echo ✓ Backend server stopped
) else (
    echo ! No Python processes found
)

echo.
echo Stopping Frontend Server (Node.js)...
taskkill /f /im node.exe 2>nul
if %errorlevel% == 0 (
    echo ✓ Frontend server stopped
) else (
    echo ! No Node.js processes found
)

echo.
echo Closing terminal windows...
taskkill /f /fi "WindowTitle eq LawChronicle Backend*" 2>nul
taskkill /f /fi "WindowTitle eq LawChronicle Frontend*" 2>nul

echo.
echo ========================================
echo    LawChronicle Application Stopped!
echo ========================================
echo.
pause
