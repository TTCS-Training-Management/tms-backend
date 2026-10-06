# TMS Backend

FastAPI backend for the Training Management System. The default local database is SQLite, so Docker and SQL Server are not required for development.

## Run locally

```powershell
cd "G:\Hệ Thống Đào Tạo\tms-backend"
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API documentation.

Run the API regression and Sprint 2 tests from this directory with `python -m unittest -v test_sprint1`.

## Demo account

- Email: `admin@tms.local`
- Password: `Admin@123`

The first start creates `tms.db` beside `main.py`, migrates the account table for Sprint 1, and seeds admin, instructor, and accountant demo accounts. Relative SQLite paths in `DATABASE_URL` are resolved from the backend directory, not the shell's current directory. Copy `.env.example` to `.env` to customize the database URL, token secret, and email delivery.

## Sprint 1 account features

- Eight account roles are supported: Guest, Student, Instructor, TA, Training Manager, Admissions, Accountant, and Admin. One account can hold multiple roles.
- Account listing supports name/email/phone search, role/status filters, and pages of 20 records.
- Password reset links are stored hashed in the database, expire after 30 minutes, and can only be used once. Account creation generates a temporary password, emails it with the activation message, and requires changing it at first sign-in; no account is created if activation email delivery is unavailable.
- Locking an account requires a reason and immediately invalidates that account's sessions. Class assignments are recorded on an account so administrators can identify classes that need handover.
- Administrators can permanently delete another account from its edit form after explicit confirmation. Deletion removes its role, class-assignment, and password-reset records; the active administrator cannot delete their own account or the last active administrator.
- The server checks role permissions for every implemented protected operation; the matrix in `main.py` documents permissions for modules built in later sprints.
- The authenticated profile returns the effective permission matrix. The frontend uses this server response to build each role's landing page and menu, rather than maintaining a separate client-side permission matrix. Unimplemented later-sprint modules show their granted access level without pretending their business workflows are already available.
- Active browser sessions renew once per minute after recent keyboard, pointer, touch, focus, input, or scroll activity. Refresh is paused when the tab is hidden or idle for 15 minutes. Each access token expires after 15 minutes, with an 8-hour absolute session limit enforced by the server. Expired sessions return to sign-in, while account-form drafts, the current screen, and filters are kept in that browser tab's session storage and scoped to the signed-in account. A successful logout revokes every session for that account and clears those drafts; if the server cannot be reached, the UI keeps the session and reports that logout could not be completed securely.

For real email delivery, configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, and `FRONTEND_URL` in `.env`. Without SMTP, account creation fails explicitly and does not leave a created account behind. In local development only, password-reset links are written to the backend log; do not use this mode in production.

## Sprint 2 user import and profile

- An administrator can download an `.xlsx` template from the Accounts page, preview the file for row-level validation, then import valid rows while invalid rows are skipped and listed in the import summary.
- Required Excel headers are `full_name`, `email`, and `roles`; optional headers are `phone`, `assigned_classes`, and `initial_password`. Multiple roles/classes can be separated by commas or semicolons. Duplicate emails, invalid emails/roles, incomplete rows, and invalid local initial passwords are reported by spreadsheet row.
- When SMTP is configured, imported accounts receive their temporary password by activation email. Without SMTP, each accepted row must provide an `initial_password` meeting the normal minimum (8 characters, at least one letter and one digit); users are required to change it on first login.
- Authenticated users can update their profile and upload an avatar from the profile dialog.

## Sprint 2 training and admissions workflows

- Training managers can create and maintain programs and reusable subjects with case-insensitive unique codes. Programs include active/inactive status. Each program can track planned, running, completed, and cancelled class lifecycle records; a program with a running class cannot be deleted, but can be set inactive. Deleting a program with no running classes removes its curriculum links and non-running class records.
- Curriculum associations reject duplicate subjects and invalid/self prerequisites. Prerequisites must be subjects already linked to the same program. Managers can remove a linked subject and persist a new sequence; removing an item clears it as a prerequisite from remaining items. A subject used by a running class cannot be deleted.
- Subject sessions have unique positive sequence numbers and respect the subject's declared session count. Managers can copy all sessions from another subject; copies are appended in sequence and rejected if they exceed the target's declared count.
- The public `/register` form has a honeypot and the public lead API limits each client IP to five accepted submissions per ten minutes. It stores only a keyed hash of the client IP for rate-limit accounting, not the raw address. The public response asks the admissions team to contact the requester soon without promising an unconfigured response-time SLA. Authenticated lead entry uses `POST /leads` and retains the selected source.

The public lead limit is in-process/database-backed and intended for this single-instance development application; deploy behind a trusted proxy and use a shared rate-limit store if running multiple API workers.
