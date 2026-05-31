@echo off
title NeuralNexus - Node 1 (port 50052)
cd /d "%~dp0neuralnexus\server"
set NODE_PORT=50052
set DB_PATH=lms.db
call "%~dp0env\Scripts\activate.bat"
python server_entry.py
pause
