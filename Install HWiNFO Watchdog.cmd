@echo off
:: Installs the EvilOS HWiNFO shared-memory watchdog (UAC prompt)
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%~dp0setup_watchdog.ps1\"'"
