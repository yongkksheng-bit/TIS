@echo off
title TIS - Tender Intelligence System

echo ============================================
echo  TIS 全栈启动脚本
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
