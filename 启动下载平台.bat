@echo off
chcp 65001 >nul
title 下载平台
cd /d "%~dp0"

python -c "import fastapi, uvicorn, Crypto, imageio_ffmpeg" 2>nul
if errorlevel 1 python -m pip install -r requirements.txt

echo =======================================================
echo  正在启动下载平台 (本机: http://127.0.0.1:8000)
echo  局域网同事访问地址会在下方启动信息中显示
echo =======================================================
echo.

rem 等服务起来后再打开浏览器 (原先是先开浏览器，常常抢在服务之前而打不开)
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"

python web_app.py --port 8000
echo.
echo 平台已退出 (如提示端口被占用，说明平台已在运行，直接用浏览器访问即可)。按任意键关闭...
pause >nul
