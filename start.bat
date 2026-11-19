@echo off
rem Today Board - double-click to start (Windows). Works from any folder, on any PC.
rem If this PC has no Python, a private copy is downloaded into tools\python (no install, no admin).
rem ASCII only, and no ( ) blocks: the folder path may contain spaces, parentheses or non-English letters.
setlocal
cd /d "%~dp0"
if exist "board-data.json" goto serve
call "%~dp0board.cmd" init
if errorlevel 9 goto nopython
:serve
call "%~dp0board.cmd" serve --open
if errorlevel 9 goto nopython
pause
exit /b 0

:nopython
echo.
echo  Python could not be prepared on this PC. See the message above.
echo  You can still LOOK at the board without it: open board.html.
echo.
pause
exit /b 1
