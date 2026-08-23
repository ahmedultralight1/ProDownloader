@echo off
title Building Pro Downloader
echo ============================================
echo   Building "Pro Downloader" program
echo   This runs ONCE. It will take a while
echo   (downloading libraries).
echo ============================================
echo.

REM ---- find a working python command, preferring a version pythonnet supports ----
REM     (pythonnet does not support Python 3.14 yet as of this writing - it needs
REM      3.8-3.13 - so we specifically look for those first via the py launcher)
set PYCMD=
for %%V in (3.12 3.11 3.13 3.10 3.9) do (
    if not defined PYCMD (
        py -%%V --version >nul 2>nul
        if not errorlevel 1 set PYCMD=py -%%V
    )
)
if not defined PYCMD (
    python --version >nul 2>nul
    if not errorlevel 1 set PYCMD=python
)
if not defined PYCMD (
    py --version >nul 2>nul
    if not errorlevel 1 set PYCMD=py
)
if not defined PYCMD (
    echo [ERROR] Could not find a working Python installation.
    echo Please install Python 3.12 from https://www.python.org/downloads/release/python-3120/
    echo and make sure "Add python.exe to PATH" is checked during install.
    echo.
    echo If you already installed Python but see a "Microsoft Store"
    echo message, go to: Settings ^> Apps ^> Advanced app settings ^>
    echo App execution aliases, and turn OFF the entries for python.exe
    echo and python3.exe. Then run this file again.
    pause
    exit /b 1
)
echo Using Python command: %PYCMD%

%PYCMD% -c "import sys; sys.exit(0 if sys.version_info[:2] <= (3,13) else 1)" >nul 2>nul
if errorlevel 1 (
    echo.
    echo ============================================
    echo   [WARNING] Your Python version is too new.
    echo   This program needs "pythonnet", which does
    echo   NOT support Python 3.14+ yet ^(only up to 3.13^).
    echo   Continuing anyway will likely fail or the
    echo   app may freeze when you interact with it.
    echo.
    echo   Please install Python 3.12 from:
    echo   https://www.python.org/downloads/release/python-3120/
    echo   ^(check "Add python.exe to PATH" during install,
    echo    no need to remove your existing Python^), then
    echo   run this file again.
    echo ============================================
    echo.
    pause
    exit /b 1
)

echo [1/5] Upgrading pip...
%PYCMD% -m pip install --upgrade pip

echo [2/5] Installing required libraries (this can take a few minutes)...
%PYCMD% -m pip install yt-dlp pyperclip pywebview pythonnet pyinstaller

echo [2b/5] Downloading ffmpeg (needed to merge video+audio and convert to MP3)...
if not exist "ffmpeg.exe" (
    powershell -Command "Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile 'ffmpeg_temp.zip'"
    powershell -Command "Expand-Archive -Path 'ffmpeg_temp.zip' -DestinationPath 'ffmpeg_temp' -Force"
    for /r "ffmpeg_temp" %%f in (ffmpeg.exe) do copy /Y "%%f" "ffmpeg.exe" >nul
    rmdir /s /q "ffmpeg_temp"
    del "ffmpeg_temp.zip"
)
if not exist "ffmpeg.exe" (
    echo [WARNING] Could not download ffmpeg automatically. High-quality downloads
    echo that need merging video+audio, and MP3 conversion, will fail without it.
)

echo [3/5] Checking the web UI folder...
if not exist "web\index.html" (
    echo [ERROR] "web\index.html" not found next to this file.
    echo Make sure the "web" folder ^(with index.html inside it^) is
    echo in the same folder as this .bat file.
    pause
    exit /b 1
)

echo [4/5] Building the exe file...
set ICONFLAG=
set ICONBIN=
if exist "ProDownloader.ico" (
    set ICONFLAG=--icon "ProDownloader.ico"
    set ICONBIN=--add-binary "ProDownloader.ico;."
) else (
    echo [NOTE] ProDownloader.ico not found next to this file - building without a custom icon.
)
if exist "ProDownloader.png" (
    set ICONBIN=%ICONBIN% --add-binary "ProDownloader.png;."
)

set FFMPEGBIN=
if exist "ffmpeg.exe" (
    set FFMPEGBIN=--add-binary "ffmpeg.exe;."
)

%PYCMD% -m PyInstaller --noconfirm --onefile --windowed ^
    --name "ProDownloader" ^
    --collect-all yt_dlp ^
    --collect-all webview ^
    --hidden-import clr ^
    --add-data "web;web" ^
    %FFMPEGBIN% %ICONFLAG% %ICONBIN% ^
    main.py

echo [5/5] Copying the finished program to your Desktop...
if not exist "dist\ProDownloader.exe" (
    echo [ERROR] Build failed - the exe file was not created.
    echo Scroll up to see the error message above.
    pause
    exit /b 1
)
copy /Y "dist\ProDownloader.exe" "%USERPROFILE%\Desktop\ProDownloader.exe" >nul

echo.
echo ============================================
echo   Done! Check your Desktop for a file named:
echo   ProDownloader.exe
echo   Send this file to anyone - it will run
echo   on their PC without installing Python.
echo ============================================
echo.
echo Notes:
echo  - This program needs the "Microsoft Edge WebView2 Runtime"
echo    to display its window. It comes pre-installed on Windows
echo    10/11 by default. If the window fails to open, install it
echo    from: https://developer.microsoft.com/microsoft-edge/webview2/
echo  - Downloaded videos are saved to Downloads\ProDownloader by
echo    default - this can be changed from the app's Settings page.
echo  - 8K/4K availability depends on the video itself - the app
echo    always grabs the best quality actually available up to the
echo    quality you chose.
echo.
pause
