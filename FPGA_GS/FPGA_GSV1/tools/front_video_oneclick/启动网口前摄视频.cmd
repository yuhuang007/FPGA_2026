@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0front_video.ps1"
if errorlevel 1 pause
