@echo off
title NeuralNexus - Client
cd /d "%~dp0neuralnexus\client"
call "%~dp0env\Scripts\activate.bat"
python client_entry.py
pause
