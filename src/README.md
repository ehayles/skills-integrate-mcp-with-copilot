# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Public activity schedules and participant lists
- Teacher login/logout and teacher-only registration/unregistration

## Getting Started

1. Install the dependencies:

   ```
   pip install -r requirements.txt
   ```

2. From the repository root, assign a teacher username and password locally:

   ```
   python -m src.assign_teacher teacher
   ```

   Enter the assigned password directly in the terminal prompts. Credentials are
   stored as salted PBKDF2-SHA256 hashes in the gitignored `src/teachers.json`,
   outside the public static directory. There are no default credentials.
   Repeat the command to add a teacher or reset their password, then restart
   the server to invalidate existing sessions. There is no account-maintenance UI.

3. Run the application from the repository root:

   ```
   python -m uvicorn src.app:app --host 0.0.0.0 --port 8000
   ```

4. Open your browser and go to:
   - Application: http://localhost:8000
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Sign up for an activity                                             |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Unregister from an activity |
| POST | `/auth/login` | Authenticate with a JSON username/password body |
| GET | `/auth/session` | Get the current teacher and CSRF token |
| POST | `/auth/logout` | Revoke the current teacher session |

Registration, unregistration, and logout require the HttpOnly session cookie
and an `X-CSRF-Token` header matching the token returned by login/session.
Anonymous users can still view activities and participants. Sessions expire
after eight hours and are cleared on restart. The UI restores login on reload
and hides editing controls when a session expires.

Set `TEACHERS_FILE` to override the credential file path. For HTTPS deployments,
set `COOKIE_SECURE=true`; local HTTP development uses non-secure cookies.
Run a single application worker: sessions and activities are process-local.
Internet-facing deployment also needs HTTPS and login rate limiting at the
deployment boundary; this development app does not provide a rate limiter.

## Tests

```
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier; names and grade levels are not stored.

All data is stored in memory, which means data will be reset when the server restarts.
