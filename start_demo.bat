@echo off
REM ==========================================================
REM  Telegram Clone 演示启动脚本：Redis + 后端，一条龙
REM
REM  注意：本文件必须存成 GBK + CRLF。
REM   - LF 换行会让 cmd 把每行拆成命令执行，直接报一片错
REM   - 在 bat 里写 chcp 65001 会让 cmd 解析指针错位（会把
REM     status 读成 tatus 这种），所以这里不切代码页
REM
REM  1) 起 Redis（原生 Windows 版，不需管理员、不需虚拟化）。
REM     私聊/群聊的实时投递依赖它：
REM       - 私聊靠 get_online_status 判断对方在不在线，没 Redis 一律
REM         False，消息静默进离线桶，对方永远收不到
REM       - 群聊靠 KEYS user:online:* 找在线成员，没 Redis 谁都收不到
REM     只有 AI 那条链路不依赖 Redis（send_personal 有本地回落）。
REM
REM  2) 清空 SSL_CERT_FILE：conda 全局设了
REM     SSL_CERT_FILE=anaconda3/ssl/cacert.pem，但该文件不存在，
REM     会让 httpx 调 https://api.deepseek.com 时报
REM     "[Errno 2] No such file or directory"，AI 回复变成"AI回复出错"。
REM
REM  3) 单 worker 启动：main.py 里默认 workers=4，演示没必要。
REM     用 --host 127.0.0.1 可避开 Windows 防火墙弹窗。
REM ==========================================================
set SSL_CERT_FILE=
set PYTHONIOENCODING=gbk:replace
set REDIS_DIR=D:\tools\redis-win
cd /d "%~dp0"

"%REDIS_DIR%\redis-cli.exe" ping >nul 2>&1
if not errorlevel 1 (
  echo   [1/2] Redis 已在运行
  goto go
)
echo   [1/2] 启动 Redis ...
start "Redis" /min "%REDIS_DIR%\redis-server.exe" "%REDIS_DIR%\redis.windows.conf"
timeout /t 3 /nobreak >nul
"%REDIS_DIR%\redis-cli.exe" ping >nul 2>&1
if errorlevel 1 (
  echo   !! Redis 没起来：私聊/群聊实时推送会不可用（AI 对话不受影响）
) else (
  echo   Redis 就绪
)

:go
echo   [2/2] 启动后端 ...
echo.
echo   演示地址: http://127.0.0.1:8000
echo   双窗口演示：开两个标签页，分别登 demo_a / demo_b
echo     demo_a  13900000001 / demo123456
echo     demo_b  13900000002 / demo123456
echo   （本窗口别关：工具调用日志会打印在这里）
echo.
D:\python\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
