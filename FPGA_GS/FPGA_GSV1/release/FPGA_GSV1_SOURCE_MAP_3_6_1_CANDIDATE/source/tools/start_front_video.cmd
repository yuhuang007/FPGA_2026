@echo off

cd /d "%~dp0"

python "%~dp0m3\console.py" --role right --bind 192.168.50.1 --board 192.168.50.2 --right-fps 15

if errorlevel 1 pause

