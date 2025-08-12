@echo off
echo ========================================
echo  Restarting LawChronicle Application
echo ========================================
echo.

echo Step 1: Stopping existing servers...
call stop_lawchronicle.bat

echo.
echo Step 2: Starting servers again...
timeout /t 2 /nobreak > nul
call start_lawchronicle.bat

echo.
echo ========================================
echo   LawChronicle Application Restarted!
echo ========================================
