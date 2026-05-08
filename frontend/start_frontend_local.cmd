@echo off
setlocal
cd /d "%~dp0"
npm.cmd run dev -- --host 127.0.0.1 --port 5174
