@echo off
title TIS - Tender Intelligence System

echo ============================================
echo  TIS - Tender Intelligence System
echo ============================================
echo.
echo  Select deployment mode:
echo  [1] Docker Compose (recommended)
echo  [2] Local dev mode
echo.

set /p CHOICE="Enter choice (1 or 2): "

if "%CHOICE%"=="1" goto docker_compose
if "%CHOICE%"=="2" goto local_dev

echo Invalid choice. Exiting.
exit /b 1

:docker_compose
echo.
echo ============================================
echo  Starting with Docker Compose...
echo ============================================
echo.

echo Pulling and starting containers...
docker compose up -d

echo.
echo Waiting for services to be ready...
call scripts\health_check.bat

echo.
echo ============================================
echo  Services started:
echo  Frontend: http://localhost:3000
echo  Backend:  http://localhost:8000
echo  API Docs: http://localhost:8000/docs
echo ============================================
goto end

:local_dev
echo.
echo ============================================
echo  Starting in Local Dev Mode...
echo ============================================
echo.

:: Start Backend
echo [1/2] Starting FastAPI Backend on port 8000...
start "TIS Backend" cmd /k "cd /d %~dp0 && python -m uvicorn app.main:app --reload --port 8000"

echo.
echo [2/2] Starting Vue Frontend on port 3000...
start "TIS Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ============================================
echo  Backend: http://localhost:8000
echo  Frontend: http://localhost:3000
echo  Press Ctrl+C in each window to stop
echo ============================================
goto end

:end
