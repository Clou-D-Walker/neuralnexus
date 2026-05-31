@echo off
title NeuralNexus - Node 3 (port 50054)
cd /d "%~dp0neuralnexus\server"
set NODE_PORT=50054
set DB_PATH=node3\lms.db
set ENV_FILE=node3\.env
call "%~dp0env\Scripts\activate.bat"
python server_entry.py
pause
