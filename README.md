# TMS Backend

FastAPI backend for the Training Management System. The default local database is SQLite, so Docker and SQL Server are not required for development.

## Run locally

```powershell
cd "G:\Hệ Thống Đào Tạo\tms-backend"
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API documentation.

Run the backend regression suites from this directory with `python -m unittest -v test_sprint1 test_sprint34`.

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

- An administrator can download an `.xlsx` template from the Accounts page, preview all valid rows and validation errors with 20-row pagination, then import valid rows while invalid rows are skipped and listed in the import summary.
- Required Excel headers are `full_name`, `email`, and `roles`; optional headers are `phone`, `assigned_classes`, and `initial_password`. Multiple roles/classes can be separated by commas or semicolons. Duplicate emails, invalid emails/roles, incomplete rows, and invalid local initial passwords are reported by spreadsheet row.
- When SMTP is configured, imported accounts receive their temporary password by activation email. Without SMTP, each accepted row must provide an `initial_password` meeting the normal minimum (8 characters, at least one letter and one digit); users are required to change it on first login.
- Authenticated users can update their profile and upload an avatar from the profile dialog.

## Sprint 2 training and admissions workflows

- Training managers can create and maintain programs and reusable subjects with case-insensitive unique codes. Programs include active/inactive status. Each program can track planned, running, completed, and cancelled class lifecycle records; a program with a running class cannot be deleted, but can be set inactive. Deleting a program with no running classes removes its curriculum links and non-running class records.
- Curriculum associations reject duplicate subjects and invalid/self prerequisites. Prerequisites must be subjects already linked to the same program. Managers can remove a linked subject and persist a new sequence; removing an item clears it as a prerequisite from remaining items. A subject used by a running class cannot be deleted.
- Subject sessions have unique positive sequence numbers and respect the subject's declared session count. Managers can copy all sessions from another subject; copies are appended in sequence and rejected if they exceed the target's declared count.
- The public `/register` form has a honeypot and the public lead API limits each client IP to five accepted submissions per ten minutes. It stores only a keyed hash of the client IP for rate-limit accounting, not the raw address. The public response asks the admissions team to contact the requester soon without promising an unconfigured response-time SLA. Authenticated lead entry uses `POST /leads` and retains the selected source.
- Sprint 2 lead management supports creating and editing lead contact details, duplicate-phone checks (including equivalent `0`, `84`, and `+84` formats), individual and bulk assignment, and append-only interaction notes with actor and timestamp. Admissions users can create and update their own assigned leads, and only see leads assigned to them; training managers and administrators can manage the full lead queue. Lead deletion is restricted to users with the Training Manager role.
- Lead search supports name, phone, or email plus status, source, assignee, and inclusive creation-date filters using `from_date` and `to_date` (`YYYY-MM-DD`). Add `page` and `page_size` to `GET /leads` for paginated results (`items`, `total`, `page`, `page_size`); requests without `page` retain the legacy list response. Lead interaction history is available at `GET /leads/{id}/interactions`, and new notes are added with `POST /leads/{id}/interactions`.

The public lead limit is in-process/database-backed and intended for this single-instance development application; deploy behind a trusted proxy and use a shared rate-limit store if running multiple API workers.

## Sprint 5–8 learning and operations workflows

- Sprint 5 attendance summaries use completed lessons and active enrollments, support a configurable absence threshold per program, and export class attendance to `.xlsx` (`GET /attendance/classes/{class_id}/summary` and `/summary.xlsx`).
- Sprint 6 assignments support file attachments, versioned student submissions, rubric templates, grading, grade publication, revision requests, and class learning materials. Uploads are limited to 20 MB and supported document/archive/image formats. Class announcements create in-app notifications and send email to enrolled students when SMTP is configured; the response reports sent, failed, and skipped email counts.
- Sprint 7 billing supports effective-dated program fee schedules, individual or bulk installment plans, overpayment prevention, immutable payment records and receipts, discount approval above 30%, debt/revenue reports, and a daily 08:00 Vietnam-time reminder worker. Configure SMTP as described above to deliver reminder emails; in-app reminders remain available without SMTP.
- Sprint 8 supports weighted final-grade components linked to published assignment grades, grade recalculation and locking, transcripts, graduation eligibility/confirmation, one-response-per-student surveys with aggregated results, and role-aware operational dashboards.
- New API routes are documented in FastAPI at `/docs`. Attendance and debt reports are `.xlsx`; the transcript export is currently `.xlsx` as well. The browser can print a transcript to PDF from the frontend.
- Run Sprint 5–8 backend checks from this directory with `python -m unittest -v test_sprint56_78`.

## Sprint 3 lead, student, class, and room workflows

- Leads move through the `new`, `contacted`, `consulting`, `trial`, `won`, and `rejected` recruitment stages. Converting a won lead moves it into the read-only `converted`/“Đã nhập học” stage. Stage changes are appended to interaction history, rejected leads require a loss reason, and `GET /leads/summary` returns per-stage counts. `POST /leads/{id}/interactions` accepts `interaction_type` (`call`, `message`, or `meeting`), `content` (or legacy `note`), and optional ISO `follow_up_at`; overdue items are available from `GET /leads/follow-ups/overdue`.
- `POST /leads/{id}/convert` converts a `won` lead without re-entering its contact details. It creates a uniquely coded student profile and a student login, sends the normal activation email, and freezes the lead in the converted stage. SMTP must be configured and delivery must succeed; otherwise no account/profile is created.
- `GET /students?q=&page=&page_size=` returns `{items,total,page,page_size}`; `GET/PATCH /students/{id}` provides protected profile and class-history access. `POST /students/{id}/status` records defer/transfer/withdraw history with an effective date and reason. Student codes, names, and phone numbers are indexed for lookup.
- `GET/POST /training/classes` lists or creates classes. List filters include query, program, lifecycle status, instructor and start-date bounds; pages are capped at 100. Classes copy their program subjects, and results include capacity, enrolled count, lesson progress, and a capacity warning. Existing nested program/class APIs remain available.
- `GET /training/classes/{id}/enrollments?page=&page_size=` returns `{items,total,page,page_size}` (page size capped at 100), including enrollment time and enrolling staff name; `POST` bulk-enrolls `{student_ids}` with duplicate and capacity checks. `GET /training/classes/{id}/subjects` returns each curriculum subject with its assigned instructor and TAs; `PUT /training/classes/{id}/subjects/{subject_id}/staff` accepts one `instructor_id` and multiple `ta_ids`. Staff roles are checked and class visibility is assignment-scoped.
- `/training/rooms` supports read/create/update/delete (referenced rooms are deactivated rather than physically deleted). Physical rooms require positive capacity and a location; online rooms require a link.

## Sprint 4 schedule, attendance, and absence workflows

- Schedule generation is a preview-then-save operation: `POST /training/classes/{id}/schedule/preview` and `/schedule` accept `{weekdays,recurrence,session_time,start_date,count,room_id,session_duration_minutes,skip_holidays,holidays,subject_session_ids,instructor_id,override_conflicts}`. `weekdays` uses Python weekday numbers (Monday `0` through Sunday `6`); `recurrence` is `weekly` or `biweekly`. The legacy single `weekday` field remains supported. Saved sessions retain their class subject and reusable subject-session references. Managers can configure recurring skip dates with `POST /training/holidays`.
- Schedule responses and the calendar endpoint `GET /training/sessions?start=&end=&class_id=&instructor_id=&room_id=` use ISO timestamps; date ranges are bounded to 94 days. Instructor/room overlaps are reported and block persistence unless a training manager/admin explicitly confirms an override. A room smaller than current class enrollment is rejected.
- `PATCH /training/sessions/{id}` edits one future unattended lesson; `POST /training/sessions/{id}/cancel` requires a reason. Both create durable audits and in-app notices for assigned staff and affected students. Past or attended lessons cannot be changed. `GET /students/me/schedule?start=&end=` derives class access from the authenticated student's active/effective-dated enrollments.
- `GET/PUT /training/sessions/{id}/attendance` returns the effective class roster and records `present`, `late`, `excused`, or `unexcused`; `/attendance/bulk-present` marks the roster present. Assigned instructors/TAs may edit only lessons scheduled for today, while training managers/admins may correct past records. Every change is audited.
- Students submit absence requests through `POST /attendance/absence-requests` using `{lesson_id,reason,evidence_ref}`; `GET /attendance/absence-requests` lists authorized requests and the assigned teaching team decides with `POST /attendance/absence-requests/{id}/decision` using `{decision:"approve"|"reject",reason}`. Approval marks attendance excused and creates an in-app student notice. `GET /notifications` lists persisted in-app notices.
- Startup `create_all` creates the Sprint 3/4 relational tables with declared foreign-key constraints, and startup migrations add the lead/interaction columns and indexes to existing databases. The regression suites use isolated project-local SQLite fixtures that are removed after testing; they never open the local `tms.db`.
