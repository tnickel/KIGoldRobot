@echo off
title AUDUSD M5 Trading Bot - ML Pipeline GUI
echo Starte ML Pipeline GUI...
cd /d "%~dp0"
python skripte\09_audusd_pipeline_gui.py
if %errorlevel% neq 0 (
    echo.
    echo [FEHLER] Die GUI konnte nicht gestartet werden.
    echo Bitte stellen Sie sicher, dass Python installiert ist und 'tkinter' verfuegbar ist.
    pause
)
