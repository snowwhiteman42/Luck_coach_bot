@echo off
set PYTHONPATH=C:\Users\Ilia\AppData\Roaming\Python\Python314\site-packages
set PYTHONIOENCODING=utf-8
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0run_bot_forever.ps1"
