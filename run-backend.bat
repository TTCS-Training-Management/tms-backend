@echo off
cd /d "G:\Hệ Thống Đào Tạo\tms-backend"
call ".\.venv\Scripts\activate.bat"
python -m uvicorn main:app --reload
