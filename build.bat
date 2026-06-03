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
echo [1/4] Cleaning old builds...
if exist dist\WordMaster rmdir /s /q dist\WordMaster >nul 2>&1
if exist build rmdir /s /q build >nul 2>&1
if exist WordMaster_%VER%.zip del WordMaster_%VER%.zip >nul 2>&1

rem compile
echo [2/4] Building with PyInstaller...
echo.

where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo pyinstaller not found, trying python -m PyInstaller...
    python -m PyInstaller main.py --onedir --name WordMaster --icon app/asset/images/icon.ico --add-data "app/asset;asset" --hidden-import PySide6.QtNetwork --hidden-import PySide6.QtMultimedia --hidden-import PySide6.QtSvg --hidden-import numpy --hidden-import librosa --hidden-import scipy --hidden-import httpx --hidden-import edge_tts --hidden-import app.ui.main_window --hidden-import app.ui.learning_tab --hidden-import app.ui.management_tab --hidden-import app.ui.stats_tab --hidden-import app.ui.settings_tab --hidden-import app.ui.settings_dialog --hidden-import app.ui.word_editor --hidden-import app.audio.player --hidden-import app.db.repository --hidden-import app.db.schema --hidden-import app.engine.sm2 --hidden-import app.fetcher.tts --hidden-import app.services.session --hidden-import app.services.settings --hidden-import app.services.spectrum --hidden-import app.services.spectrum_painter --hidden-import app.services.image --hidden-import app.services.text --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineQuick --exclude-module PySide6.QtBluetooth --exclude-module PySide6.QtNfc --exclude-module PySide6.QtPositioning --exclude-module PySide6.QtSensors --exclude-module PySide6.QtXml --exclude-module PySide6.QtSql --exclude-module PySide6.QtTest --exclude-module PySide6.QtHelp --exclude-module PySide6.QtDesigner --exclude-module PySide6.QtNetworkAuth --exclude-module PySide6.QtRemoteObjects --exclude-module PySide6.QtWebSockets --exclude-module PySide6.QtSerialPort --exclude-module IPython --exclude-module jupyter --exclude-module matplotlib --windowed --clean --noconfirm
) else (
    pyinstaller main.py --onedir --name WordMaster --icon app/asset/images/icon.ico --add-data "app/asset;asset" --hidden-import PySide6.QtNetwork --hidden-import PySide6.QtMultimedia --hidden-import PySide6.QtSvg --hidden-import numpy --hidden-import librosa --hidden-import scipy --hidden-import httpx --hidden-import edge_tts --hidden-import app.ui.main_window --hidden-import app.ui.learning_tab --hidden-import app.ui.management_tab --hidden-import app.ui.stats_tab --hidden-import app.ui.settings_tab --hidden-import app.ui.settings_dialog --hidden-import app.ui.word_editor --hidden-import app.audio.player --hidden-import app.db.repository --hidden-import app.db.schema --hidden-import app.engine.sm2 --hidden-import app.fetcher.tts --hidden-import app.services.session --hidden-import app.services.settings --hidden-import app.services.spectrum --hidden-import app.services.spectrum_painter --hidden-import app.services.image --hidden-import app.services.text --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineQuick --exclude-module PySide6.QtBluetooth --exclude-module PySide6.QtNfc --exclude-module PySide6.QtPositioning --exclude-module PySide6.QtSensors --exclude-module PySide6.QtXml --exclude-module PySide6.QtSql --exclude-module PySide6.QtTest --exclude-module PySide6.QtHelp --exclude-module PySide6.QtDesigner --exclude-module PySide6.QtNetworkAuth --exclude-module PySide6.QtRemoteObjects --exclude-module PySide6.QtWebSockets --exclude-module PySide6.QtSerialPort --exclude-module IPython --exclude-module jupyter --exclude-module matplotlib --windowed --clean --noconfirm
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

rem remove top-level exe
if exist dist\WordMaster.exe del dist\WordMaster.exe

rem copy words.db
if exist app\db\words.db (
    if not exist dist\WordMaster\app\db mkdir dist\WordMaster\app\db
    copy /y app\db\words.db dist\WordMaster\app\db\words.db >nul
    echo [INFO] words.db copied
)

echo [3/4] Build complete!

rem create ZIP
echo [4/4] Creating WordMaster_%VER%.zip...
python -c "import shutil,os;v='%VER%';shutil.make_archive('WordMaster_'+v,'zip','dist','WordMaster');s=os.path.getsize('WordMaster_'+v+'.zip')//1048576;print('ZIP size: '+str(s)+' MB')"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   Done! WordMaster_%VER%.zip created
    echo ========================================
) else (
    echo [ERROR] ZIP creation failed!
)

echo.
pause
