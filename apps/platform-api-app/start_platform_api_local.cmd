@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=c:\Users\erhan\OneDrive\Desktop\ERHAN\AI_DATASCIENCE_TEAM\ai-data-science-team
set DATABASE_URL=sqlite:///./platform_dev.db
set DEPLOYMENT_PROFILE=local
python -m uvicorn platform_api.asgi:app --host 127.0.0.1 --port 8010
