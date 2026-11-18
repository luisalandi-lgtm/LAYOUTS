@echo off
rem Ricostruisce release\OneViewLayoutGenerator.exe (richiede: pip install pyinstaller)
py -m PyInstaller --noconfirm --onefile --windowed --name OneViewLayoutGenerator --distpath release layout_generator.py
rmdir /s /q build 2>nul
del OneViewLayoutGenerator.spec 2>nul
