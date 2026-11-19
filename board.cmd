@echo off
rem Today Board - run the tool with whatever Python this PC has (Windows).
rem   board.cmd list            board.cmd card set <id> zone=now title="..."
rem Order: private copy in tools\python  ->  py -3  ->  python  ->  python3  ->  download a private copy.
rem ASCII only, and no ( ) blocks: the folder path may contain spaces, parentheses or non-English letters.
setlocal
set "HERE=%~dp0"
set "PRIV=%HERE%tools\python\python.exe"

if exist "%PRIV%" goto usepriv
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 goto usepy
python -c "import sys" >nul 2>nul
if not errorlevel 1 goto usepython
python3 -c "import sys" >nul 2>nul
if not errorlevel 1 goto usepython3

powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%tools\get-python.ps1"
if exist "%PRIV%" goto usepriv
exit /b 9

:usepriv
"%PRIV%" -X utf8 "%HERE%tools\board.py" %*
exit /b %ERRORLEVEL%
:usepy
py -3 -X utf8 "%HERE%tools\board.py" %*
exit /b %ERRORLEVEL%
:usepython
python -X utf8 "%HERE%tools\board.py" %*
exit /b %ERRORLEVEL%
:usepython3
python3 -X utf8 "%HERE%tools\board.py" %*
exit /b %ERRORLEVEL%
