@echo off
title NeuralNexus - Cluster Launcher
echo Starting NeuralNexus 3-node cluster...
echo.

start "NeuralNexus - Node 1 (port 50052)" "%~dp0start_node1.bat"
timeout /t 1 /nobreak >nul
start "NeuralNexus - Node 2 (port 50053)" "%~dp0start_node2.bat"
timeout /t 1 /nobreak >nul
start "NeuralNexus - Node 3 (port 50054)" "%~dp0start_node3.bat"

echo All 3 nodes launched in separate windows.
echo Wait ~2 seconds for Raft leader election to complete.
echo Then run start_client.bat in a new terminal.
echo.
pause
