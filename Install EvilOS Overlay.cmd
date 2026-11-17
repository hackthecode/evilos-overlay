@echo off
:: Runs install.ps1 as administrator (UAC prompt)
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%~dp0install.ps1\"'"
