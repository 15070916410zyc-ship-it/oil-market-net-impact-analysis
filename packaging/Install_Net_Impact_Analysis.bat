@echo off
chcp 65001 > nul
title Install Multiscale Net-Impact Analysis System

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
pause
