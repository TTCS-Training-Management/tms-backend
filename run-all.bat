@echo off
start "TMS Backend" cmd /k "cd /d ^"G:\Hệ Thống Đào Tạo\tms-backend^" && call .\.venv\Scripts\activate.bat && python -m uvicorn main:app --reload"
timeout /t 3 >nul
start "TMS Frontend" cmd /k "cd /d ^"G:\Hệ Thống Đào Tạo\tms-frontend^" && npm run dev -- --host 0.0.0.0"
