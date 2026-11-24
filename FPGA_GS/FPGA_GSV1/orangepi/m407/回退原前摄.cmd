@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher.ps1" -Action Stop -NoPause
if errorlevel 1 (pause & exit /b 1)
call "%~dp0..\oneclick\启动前摄预览.cmd"
