@echo off
title NeuralNexus - Node 2 (port 50053)
cd /d "%~dp0neuralnexus\server"
set NODE_PORT=50053
set DB_PATH=node2\lms.db
REM Temporarily point .env loader to node2's .env
set ENV_FILE=node2\.env
call "%~dp0env\Scripts\activate.bat"
python server_entry.py
pause
