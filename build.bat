@echo off
title WordMaster Build
echo ========================================
echo   WordMaster Build Script
echo ========================================
echo.

rem get version
for /f "tokens=2 delims==" %%a in ('findstr /b "VERSION_NAME" main.py') do set "RAW=%%a"
set RAW=%RAW: =%
set RAW=%RAW:"=%
for /f "delims=#" %%a in ("%RAW%") do set "VER=%%a"
if "%VER%"=="" set VER=v1.0.0
echo Version: %VER%
echo.

rem clean
echo [1/5] Cleaning...
if exist dist\WordMaster rmdir /s /q dist\WordMaster >nul 2>&1
if exist build rmdir /s /q build >nul 2>&1
if exist WordMaster_%VER%.zip del WordMaster_%VER%.zip >nul 2>&1

rem warm numba JIT
echo [2/5] Warming numba JIT...
python -c "import numpy as np; import librosa; librosa.stft(np.zeros(22050,dtype=np.float32),n_fft=2048,hop_length=512); print('numba warm')"

rem compile
echo [3/5] Building...

set FLAGS=--onedir --name WordMaster --icon app/asset/images/ABC.ico
set FLAGS=%FLAGS% --add-data "app/asset;asset"
set FLAGS=%FLAGS% --hidden-import PySide6.QtNetwork --hidden-import PySide6.QtMultimedia --hidden-import PySide6.QtSvg
set FLAGS=%FLAGS% --hidden-import numpy --hidden-import librosa --hidden-import scipy
set FLAGS=%FLAGS% --hidden-import httpx --hidden-import edge_tts
set FLAGS=%FLAGS% --hidden-import app.ui.main_window --hidden-import app.ui.learning_tab
set FLAGS=%FLAGS% --hidden-import app.ui.management_tab --hidden-import app.ui.stats_tab
set FLAGS=%FLAGS% --hidden-import app.ui.settings_tab --hidden-import app.ui.settings_dialog
set FLAGS=%FLAGS% --hidden-import app.ui.word_editor --hidden-import app.audio.player
set FLAGS=%FLAGS% --hidden-import app.db.repository --hidden-import app.db.schema
set FLAGS=%FLAGS% --hidden-import app.engine.sm2 --hidden-import app.fetcher.tts
set FLAGS=%FLAGS% --hidden-import app.services.session --hidden-import app.services.settings
set FLAGS=%FLAGS% --hidden-import app.services.spectrum --hidden-import app.services.spectrum_painter
set FLAGS=%FLAGS% --hidden-import app.services.image --hidden-import app.services.text
set FLAGS=%FLAGS% --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineCore
set FLAGS=%FLAGS% --exclude-module PySide6.QtWebEngineQuick --exclude-module PySide6.QtBluetooth
set FLAGS=%FLAGS% --exclude-module PySide6.QtNfc --exclude-module PySide6.QtPositioning
set FLAGS=%FLAGS% --exclude-module PySide6.QtSensors --exclude-module PySide6.QtXml
set FLAGS=%FLAGS% --exclude-module PySide6.QtSql --exclude-module PySide6.QtTest
set FLAGS=%FLAGS% --exclude-module PySide6.QtHelp --exclude-module PySide6.QtDesigner
set FLAGS=%FLAGS% --exclude-module PySide6.QtNetworkAuth --exclude-module PySide6.QtRemoteObjects
set FLAGS=%FLAGS% --exclude-module PySide6.QtWebSockets --exclude-module PySide6.QtSerialPort
set FLAGS=%FLAGS% --exclude-module IPython --exclude-module jupyter --exclude-module matplotlib
set FLAGS=%FLAGS% --windowed --clean --noconfirm

where pyinstaller >nul 2>&1
if %errorlevel% equ 0 (
    pyinstaller main.py %FLAGS%
) else (
    python -m PyInstaller main.py %FLAGS%
)

if %errorlevel% neq 0 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

rem remove top-level exe
if exist dist\WordMaster.exe del dist\WordMaster.exe

rem copy words.db
if exist app\db\words.db (
    if not exist dist\WordMaster\app\db mkdir dist\WordMaster\app\db
    copy /y app\db\words.db dist\WordMaster\app\db\words.db >nul
)

rem copy numba cache
python -c "import os,shutil; dst='dist/WordMaster/_internal/librosa'; src=os.path.dirname(__import__('librosa').__file__); [shutil.copytree(os.path.join(src,m),os.path.join(dst,m),dirs_exist_ok=True) for m in ['util/__pycache__','core/__pycache__'] if os.path.exists(os.path.join(src,m))]; print('numba cached')"

echo [4/5] Complete!

rem create ZIP
echo [5/5] Zipping...
python -c "import shutil,os;v='%VER%';shutil.make_archive('WordMaster_'+v,'zip','dist','WordMaster');s=os.path.getsize('WordMaster_'+v+'.zip')//1048576;print('ZIP: '+str(s)+' MB')"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   Done! WordMaster_%VER%.zip
    echo ========================================
) else (
    echo ZIP failed!
)

echo.
pause
