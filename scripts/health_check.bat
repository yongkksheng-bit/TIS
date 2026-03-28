@echo off
setlocal enabledelayedexpansion

set "BACKEND_URL=http://localhost:8000"
set "MAX_RETRIES=30"
set "RETRY_INTERVAL=2"

echo Checking backend at %BACKEND_URL%...
for /L %%i in (1,1,%MAX_RETRIES%) do (
    curl -sf "%BACKEND_URL%/health" > nul 2>&1
    if !errorlevel!==0 (
        echo Backend is healthy
        exit /b 0
    )
    echo Attempt %%i/!MAX_RETRIES!: Backend not ready, waiting...
    timeout /t %RETRY_INTERVAL% /nobreak > nul
)
echo Backend health check failed
exit /b 1
