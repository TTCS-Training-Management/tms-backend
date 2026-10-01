# TMS Backend

FastAPI backend for the Training Management System. The default local database is SQLite, so Docker and SQL Server are not required for development.

## Run locally

```powershell
cd "G:\Hệ Thống Đào Tạo\tms-backend"
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API documentation.

## Demo account

- Email: `admin@tms.local`
- Password: `Admin@123`

The first start creates `tms.db` and seeds admin, lecturer, and accountant demo accounts. Copy `.env.example` to `.env` to customize the database URL and token secret.
