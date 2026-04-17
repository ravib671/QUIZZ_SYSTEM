# Quiz System (Weekly Viva Automation)

A local web application to manage weekly MCQ viva quizzes for students and faculty.

## Features

### Student Portal
- Login with student credentials.
- View currently enabled quiz (one attempt only).
- Attempt enabled quiz for the current week/date.
- For each attempt, student receives **random 5 questions** from the uploaded question pool.
- View date-wise history of attempted quizzes and marks (out of 5).
- View running average converted to **out of 10**.

### Admin Portal
- Login with admin credentials.
- Upload quiz questions via CSV (6 columns):
  1. question
  2. option_a
  3. option_b
  4. option_c
  5. option_d
  6. correct_option (`A` / `B` / `C` / `D`)
- Enable/disable quizzes for student attempts.
- View all quizzes date-wise.
- View all student marks date-wise and running average out of 10.
- Upload supports **5 to 20 questions per quiz**.
- Set quiz timer (minutes). Quiz auto-submits when timer expires.
- Admin can monitor waiting-count and explicitly start quiz; students can attempt only after start command.
- Quiz creation now requires `Sem`, `Section`, and `Subject Code` (subject must be assigned to that faculty).
- Status values in admin dashboard: `Not Started`, `Started`, `Completed`, `Expired`.
- Semester cleanup supports **Download final sheet + delete data** flow.

### Super Admin
- Uses same login page with hardcoded credentials via env vars:
  - `SUPER_ADMIN_USERNAME` (default: `superadmin`)
  - `SUPER_ADMIN_PASSWORD` (default: `Super@123`)
- Can create faculty admin accounts (`faculty code`, `name`, `email`, username/password).
- Can assign subject combinations (`sem`, `section`, `subject_code`) to each admin.
- Can reset password for any existing user (student/admin) with a temporary strong password.

## Tech Stack
- Python 3 + Flask
- MySQL
- Jinja2 templates + Bootstrap (CDN)

## Project Structure

- `app.py` - Flask app entrypoint
- `db.py` - MySQL connection helper
- `schema.sql` - Database schema and sample users
- `requirements.txt` - Python dependencies
- `templates/` - HTML templates
- `static/` - static assets

## Setup

1. Create MySQL database:

```sql
CREATE DATABASE quizz_system;
```

2. Configure environment variables:

```bash
export DB_HOST=127.0.0.1
export DB_PORT=3306
export DB_NAME=quizz_system
export DB_USER=root
export DB_PASSWORD=your_password
export SECRET_KEY=change-me
```

3. Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Initialize schema:

```bash
mysql -u root -p quizz_system < schema.sql
```

5. Run app:

```bash
python app.py
```

Then open: `http://127.0.0.1:5000`

## Default Users
Loaded by `schema.sql`:
- Admin: `admin1 / admin123`
- Students:
  - `student1 / stud123`
  - `student2 / stud123`

> Passwords are plain text for local demo simplicity. For production, use password hashing and HTTPS.

## CSV Format Example

```csv
What is 2+2?,1,2,3,4,D
Capital of France?,Berlin,Rome,Paris,Madrid,C
```

## Notes
- Each quiz can be attempted **once per student**.
- Only quizzes marked `enabled=1` appear in student dashboard.
- Running average out of 10 = `(avg(score_out_of_5) / 5) * 10`.
