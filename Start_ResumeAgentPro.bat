@echo off
title ResumeAgent Pro - Career OS
cd /d "%~dp0"
echo =================================================================
echo  ResumeAgent Pro - Launching Career Operating System
echo  Debanjan Kakati (BITS Pilani)
echo =================================================================
echo.
echo Starting application server and opening your browser...
echo If the browser does not open automatically, visit: http://127.0.0.1:8000
echo.

if exist "ResumeAgentPro.exe" (
    echo Starting from standalone executable...
    start "" "ResumeAgentPro.exe"
) else (
    echo Starting via Python environment...
    python run.py
)

exit
