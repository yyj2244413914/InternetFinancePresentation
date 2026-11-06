@echo off
cd /d "%~dp0"
title Build Demo Package

echo [1/4] Export slides.html ...
call python -X utf8 scripts\make_offline_html.py
if errorlevel 1 ( echo [FAIL] Export failed. Check above. & pause & exit /b 1 )

echo [2/4] Customize slides ...
call python -X utf8 scripts\customize_slides.py

echo [3/4] Build demo folder ...
call python -X utf8 scripts\make_demo_package.py
if errorlevel 1 ( echo [FAIL] Build failed. Check above. & pause & exit /b 1 )

echo [4/4] Preflight check ...
call python -X utf8 scripts\preflight_check.py

echo.
echo Done! Open the demo folder and double-click the slides.html
pause
