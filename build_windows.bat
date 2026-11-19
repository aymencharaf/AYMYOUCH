@echo off
setlocal
py -m pip install --upgrade pip
py -m pip install -r requirements.txt pyinstaller
py -m PyInstaller --noconfirm --clean --windowed --name AYMTECH_PRO ^
    --add-data "assets;assets" ^
    --icon "assets\logo_a.png" ^
    main.py
echo.
echo Build complete. EXE location: dist\AYMTECH_PRO\AYMTECH_PRO.exe
pause
