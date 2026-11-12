@echo off
setlocal
py -m pip install --upgrade pip
py -m pip install -r requirements.txt pyinstaller
py -m PyInstaller --noconfirm --clean --windowed --name AYMEN_Phone_Service main.py
echo.
echo Build complete. EXE location: dist\AYMEN_Phone_Service\AYMEN_Phone_Service.exe
pause
