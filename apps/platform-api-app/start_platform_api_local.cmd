@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=c:\Users\erhan\OneDrive\Desktop\ERHAN\AI_DATASCIENCE_TEAM
set DATABASE_URL=sqlite:///./platform_dev.db
set DEPLOYMENT_PROFILE=local
set AUTH_MODE=dev
set DEV_AUTH_TOKEN=dev
set DEV_AUTH_EMAIL=dev@example.local
python -m uvicorn platform_api.asgi:app --host 127.0.0.1 --port 8010
