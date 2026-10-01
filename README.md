# TMS Backend

FastAPI backend for the Training Management System. The default local database is SQLite, so Docker and SQL Server are not required for development.

## Run locally

```powershell
cd "G:\Hệ Thống Đào Tạo\tms-backend"
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API documentation.

## Use SQL Server

Install Microsoft ODBC Driver 18 for SQL Server on the machine running the API. The Python `pyodbc` package is included in `requirements.txt` and is installed by the command above.

Copy `.env.example` to `.env`, then replace the `DATABASE_URL` value with a SQL Server connection URL:

```env
DATABASE_URL=mssql+pyodbc://<username>:<password>@<server>/<database>?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

Create the database in SQL Server before starting the API. On startup, the backend creates its tables and seeds demo users if the users table is empty. `TrustServerCertificate=yes` is for local development only; use a valid trusted certificate in production. URL-encode special characters in the username or password.

## Demo account

- Email: `admin@tms.local`
- Password: `Admin@123`

The first start creates `tms.db` and seeds admin, lecturer, and accountant demo accounts. Copy `.env.example` to `.env` to customize the database URL and token secret.
