import csv
import io
import os
import re
import random
from io import BytesIO
from datetime import date
import time
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from openpyxl import Workbook
from werkzeug.security import check_password_hash, generate_password_hash

from db import execute_query, fetch_all, fetch_one

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-me")

SUPER_ADMIN_USERNAME = os.getenv("SUPER_ADMIN_USERNAME", "superadmin")
SUPER_ADMIN_PASSWORD = os.getenv("SUPER_ADMIN_PASSWORD", "Super@123")


def is_password_strong(password):
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[^A-Za-z0-9]", password):
        return False
    return True


def verify_password(stored_password, entered_password):
    if stored_password.startswith(("pbkdf2:", "scrypt:")):
        return check_password_hash(stored_password, entered_password)
    return stored_password == entered_password


def valid_batch_for_section(section, batch):
    if not re.fullmatch(r"[A-Z]", section or ""):
        return False
    return batch in {f"{section}1", f"{section}2", f"{section}3"}


def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login first.", "warning")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("Unauthorized access.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == SUPER_ADMIN_USERNAME and password == SUPER_ADMIN_PASSWORD:
            session["user_id"] = 0
            session["username"] = SUPER_ADMIN_USERNAME
            session["full_name"] = "Super Admin"
            session["role"] = "super_admin"
            flash("Super admin login successful.", "success")
            return redirect(url_for("dashboard"))

        user = fetch_one(
            "SELECT id, username, full_name, role, password FROM users WHERE username=%s",
            (username,),
        )

        if user and verify_password(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user.get("full_name")
            session["role"] = user["role"]
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "danger")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        usn = request.form.get("usn", "").strip().upper()
        full_name = request.form.get("full_name", "").strip()
        sem = request.form.get("sem", "").strip()
        section = request.form.get("section", "").strip().upper()
        batch = request.form.get("batch", "").strip().upper()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not usn or not full_name or not sem or not section or not batch or not password or not confirm_password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        if not re.fullmatch(r"[A-Z0-9]{6,20}", usn):
            flash("USN must be 6-20 characters (A-Z, 0-9 only).", "danger")
            return redirect(url_for("register"))
        if not sem.isdigit() or int(sem) < 1 or int(sem) > 8:
            flash("Semester must be between 1 and 8.", "danger")
            return redirect(url_for("register"))
        if not re.fullmatch(r"[A-Z]", section):
            flash("Section must be a single letter A-Z.", "danger")
            return redirect(url_for("register"))
        if not valid_batch_for_section(section, batch):
            flash("Batch must match section (e.g. A1/A2/A3 for section A).", "danger")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        if not is_password_strong(password):
            flash(
                "Password must be at least 8 chars and include uppercase, lowercase, digit, and special character.",
                "danger",
            )
            return redirect(url_for("register"))

        existing_user = fetch_one("SELECT id FROM users WHERE username=%s", (usn,))
        if existing_user:
            flash("USN already registered. Please login.", "warning")
            return redirect(url_for("login"))

        hashed_password = generate_password_hash(password)
        execute_query(
            "INSERT INTO users (username, full_name, password, role, sem, section, batch) VALUES (%s, %s, %s, 'student', %s, %s, %s)",
            (usn, full_name, hashed_password, int(sem), section, batch),
        )
        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required()
def dashboard():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    if session.get("role") == "super_admin":
        return redirect(url_for("super_admin_dashboard"))
    return redirect(url_for("student_dashboard"))


@app.route("/super-admin", methods=["GET", "POST"])
@login_required(role="super_admin")
def super_admin_dashboard():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create_admin":
            faculty_code = request.form.get("faculty_code", "").strip().upper()
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            if not faculty_code or not full_name or not username or not password:
                flash("Faculty code, name, username and password are required.", "danger")
                return redirect(url_for("super_admin_dashboard"))
            if not is_password_strong(password):
                flash("Password must be strong.", "danger")
                return redirect(url_for("super_admin_dashboard"))
            execute_query(
                """
                INSERT INTO users (username, faculty_code, full_name, email, password, role)
                VALUES (%s, %s, %s, %s, %s, 'admin')
                """,
                (username, faculty_code, full_name, email, generate_password_hash(password)),
            )
            flash("Admin created successfully.", "success")
            return redirect(url_for("super_admin_dashboard"))
        if action == "assign_subject":
            admin_id = request.form.get("admin_id", "").strip()
            sem = request.form.get("sem", "").strip()
            section = request.form.get("section", "").strip().upper()
            subject_code = request.form.get("subject_code", "").strip().upper()
            if not admin_id or not sem or not section or not subject_code:
                flash("All assignment fields are required.", "danger")
                return redirect(url_for("super_admin_dashboard"))
            if not sem.isdigit() or int(sem) < 1 or int(sem) > 8:
                flash("Semester must be between 1 and 8.", "danger")
                return redirect(url_for("super_admin_dashboard"))
            if not re.fullmatch(r"[A-Z]{3,4}", subject_code):
                flash("Subject code must be 3-4 uppercase letters.", "danger")
                return redirect(url_for("super_admin_dashboard"))
            execute_query(
                """
                INSERT INTO admin_subject_assignments (admin_id, sem, section, subject_code)
                VALUES (%s, %s, %s, %s)
                """,
                (int(admin_id), int(sem), section, subject_code),
            )
            flash("Subject assignment saved.", "success")
            return redirect(url_for("super_admin_dashboard"))
        if action == "reset_user_password":
            username = request.form.get("username", "").strip()
            new_password = request.form.get("new_password", "").strip()
            if not username or not new_password:
                flash("Username and new password are required.", "danger")
                return redirect(url_for("super_admin_dashboard"))
            if not is_password_strong(new_password):
                flash("New password must be strong.", "danger")
                return redirect(url_for("super_admin_dashboard"))
            target = fetch_one("SELECT id, role FROM users WHERE username=%s", (username,))
            if not target:
                flash("User not found.", "warning")
                return redirect(url_for("super_admin_dashboard"))
            execute_query(
                "UPDATE users SET password=%s WHERE id=%s",
                (generate_password_hash(new_password), target["id"]),
            )
            flash(f"Password reset successful for {username}.", "success")
            return redirect(url_for("super_admin_dashboard"))
        if action == "delete_admin":
            admin_id = request.form.get("admin_id", "").strip()
            if not admin_id or not admin_id.isdigit():
                flash("Valid admin ID is required.", "danger")
                return redirect(url_for("super_admin_dashboard"))
            target_admin = fetch_one(
                "SELECT id, full_name FROM users WHERE id=%s AND role='admin'",
                (int(admin_id),),
            )
            if not target_admin:
                flash("Admin not found.", "warning")
                return redirect(url_for("super_admin_dashboard"))
            execute_query("DELETE FROM admin_subject_assignments WHERE admin_id=%s", (int(admin_id),))
            execute_query("DELETE FROM quizzes WHERE admin_id=%s", (int(admin_id),))
            execute_query("DELETE FROM users WHERE id=%s AND role='admin'", (int(admin_id),))
            flash(f"Admin {target_admin['full_name']} deleted successfully.", "success")
            return redirect(url_for("super_admin_dashboard"))

    admins = fetch_all(
        "SELECT id, username, faculty_code, full_name, email FROM users WHERE role='admin' ORDER BY username ASC"
    )
    assignments = fetch_all(
        """
        SELECT a.id, u.full_name AS admin_name, a.sem, a.section, a.subject_code
        FROM admin_subject_assignments a
        JOIN users u ON u.id=a.admin_id
        ORDER BY u.full_name, a.sem, a.section, a.subject_code
        """
    )
    return render_template("super_admin_dashboard.html", admins=admins, assignments=assignments)


@app.route("/student")
@login_required(role="student")
def student_dashboard():
    user_id = session["user_id"]
    student = fetch_one("SELECT sem, section, batch FROM users WHERE id=%s", (user_id,))
    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("logout"))

    available_quizzes = fetch_all(
        """
        SELECT q.id, q.title, q.quiz_date, q.subject_code, q.sem, q.section, q.batch,
               CASE WHEN qa.id IS NULL THEN 0 ELSE 1 END AS attempted
        FROM quizzes q
        LEFT JOIN quiz_attempts qa ON qa.quiz_id=q.id AND qa.student_id=%s
        WHERE q.enabled=1
          AND q.quiz_date = CURDATE()
          AND q.sem=%s
          AND q.section=%s
          AND (q.batch=%s OR q.batch IS NULL)
        ORDER BY q.quiz_date DESC
        """,
        (user_id, student["sem"], student["section"], student["batch"]),
    )

    history = fetch_all(
        """
        SELECT q.title, q.quiz_date, q.subject_code, q.sem, q.section, q.batch, qa.score, qa.total_questions,
               ROUND((qa.score / NULLIF(qa.total_questions, 0)) * 5, 2) AS marks_out_of_5
        FROM quiz_attempts qa
        JOIN quizzes q ON q.id=qa.quiz_id
        WHERE qa.student_id=%s
        ORDER BY q.quiz_date DESC
        """,
        (user_id,),
    )

    running_avg = fetch_one(
        """
        SELECT
            ROUND(
                (
                    COALESCE(SUM(qa.score / NULLIF(qa.total_questions, 0) * 5), 0)
                    / NULLIF(COUNT(DISTINCT q.id), 0)
                    / 5
                ) * 10,
                2
            ) AS avg_out_of_10
        FROM quizzes q
        LEFT JOIN quiz_attempts qa
            ON qa.quiz_id=q.id AND qa.student_id=%s
        WHERE q.quiz_date <= CURDATE()
          AND q.sem=%s
          AND q.section=%s
          AND (q.batch=%s OR q.batch IS NULL)
        """,
        (user_id, student["sem"], student["section"], student["batch"]),
    )

    return render_template(
        "student_dashboard.html",
        available_quizzes=available_quizzes,
        history=history,
        avg_out_of_10=running_avg["avg_out_of_10"] if running_avg else None,
    )


@app.route("/student/profile", methods=["GET", "POST"])
@login_required(role="student")
def student_profile():
    user_id = session["user_id"]
    student = fetch_one(
        "SELECT username, full_name, sem, section, batch FROM users WHERE id=%s AND role='student'",
        (user_id,),
    )
    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("student_dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        sem = request.form.get("sem", "").strip()
        section = request.form.get("section", "").strip().upper()
        batch = request.form.get("batch", "").strip().upper()

        if not full_name or not sem or not section or not batch:
            flash("All profile fields are required.", "danger")
            return redirect(url_for("student_profile"))
        if not sem.isdigit() or int(sem) < 1 or int(sem) > 8:
            flash("Semester must be between 1 and 8.", "danger")
            return redirect(url_for("student_profile"))
        if not re.fullmatch(r"[A-Z]", section):
            flash("Section must be a single letter A-Z.", "danger")
            return redirect(url_for("student_profile"))
        if not valid_batch_for_section(section, batch):
            flash("Batch must match section (e.g. A1/A2/A3 for section A).", "danger")
            return redirect(url_for("student_profile"))

        execute_query(
            "UPDATE users SET full_name=%s, sem=%s, section=%s, batch=%s WHERE id=%s AND role='student'",
            (full_name, int(sem), section, batch, user_id),
        )
        session["full_name"] = full_name
        flash("Profile updated successfully.", "success")
        return redirect(url_for("student_dashboard"))

    return render_template("student_profile.html", student=student)


@app.route("/student/change-password", methods=["GET", "POST"])
@login_required(role="student")
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        user = fetch_one(
            "SELECT id, password FROM users WHERE id=%s",
            (session["user_id"],),
        )
        if not user or not verify_password(user["password"], current_password):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("change_password"))

        if new_password != confirm_password:
            flash("New password and confirm password do not match.", "danger")
            return redirect(url_for("change_password"))

        if not is_password_strong(new_password):
            flash(
                "Password must be at least 8 chars and include uppercase, lowercase, digit, and special character.",
                "danger",
            )
            return redirect(url_for("change_password"))

        execute_query(
            "UPDATE users SET password=%s WHERE id=%s",
            (generate_password_hash(new_password), session["user_id"]),
        )
        flash("Password changed successfully.", "success")
        return redirect(url_for("student_dashboard"))

    return render_template("change_password.html")


@app.route("/admin/change-password", methods=["GET", "POST"])
@login_required(role="admin")
def admin_change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        user = fetch_one(
            "SELECT id, password FROM users WHERE id=%s",
            (session["user_id"],),
        )
        if not user or not verify_password(user["password"], current_password):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("admin_change_password"))

        if new_password != confirm_password:
            flash("New password and confirm password do not match.", "danger")
            return redirect(url_for("admin_change_password"))

        if not is_password_strong(new_password):
            flash(
                "Password must be at least 8 chars and include uppercase, lowercase, digit, and special character.",
                "danger",
            )
            return redirect(url_for("admin_change_password"))

        execute_query(
            "UPDATE users SET password=%s WHERE id=%s",
            (generate_password_hash(new_password), session["user_id"]),
        )
        flash("Password changed successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("change_password.html", back_url=url_for("admin_dashboard"))


@app.route("/student/quiz/<int:quiz_id>", methods=["GET", "POST"])
@login_required(role="student")
def attempt_quiz(quiz_id):
    user_id = session["user_id"]

    student = fetch_one("SELECT sem, section, batch FROM users WHERE id=%s", (user_id,))
    quiz = fetch_one(
        "SELECT id, title, enabled, quiz_date, duration_minutes, started_at, sem, section, batch FROM quizzes WHERE id=%s",
        (quiz_id,),
    )
    if not quiz or quiz["enabled"] != 1 or str(quiz["quiz_date"]) != str(date.today()):
        flash("Quiz is not available for today.", "warning")
        return redirect(url_for("student_dashboard"))
    if (
        not student
        or int(quiz["sem"]) != int(student["sem"])
        or quiz["section"] != student["section"]
        or (quiz.get("batch") and quiz["batch"] != student["batch"])
    ):
        flash("This quiz is not assigned to your semester/section.", "warning")
        return redirect(url_for("student_dashboard"))

    already_attempted = fetch_one(
        "SELECT id FROM quiz_attempts WHERE quiz_id=%s AND student_id=%s",
        (quiz_id, user_id),
    )
    if already_attempted:
        flash("You already attempted this quiz.", "info")
        return redirect(url_for("student_dashboard"))

    if not quiz.get("started_at"):
        execute_query(
            """
            INSERT INTO quiz_waiting (quiz_id, student_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE joined_at=CURRENT_TIMESTAMP
            """,
            (quiz_id, user_id),
        )
        return render_template("quiz_waiting.html", quiz=quiz)

    all_questions = fetch_all(
        """
        SELECT id, question, option_a, option_b, option_c, option_d, correct_option
        FROM quiz_questions
        WHERE quiz_id=%s
        ORDER BY id ASC
        """,
        (quiz_id,),
    )

    if len(all_questions) < 5:
        flash("Quiz is not configured correctly. Minimum 5 questions are required.", "danger")
        return redirect(url_for("student_dashboard"))

    session_key = f"quiz_{quiz_id}_student_{user_id}_questions"
    selected_question_ids = session.get(session_key)

    if not selected_question_ids:
        selected_questions = random.sample(all_questions, 5)
        selected_question_ids = [q["id"] for q in selected_questions]
        session[session_key] = selected_question_ids
    else:
        questions_map = {q["id"]: q for q in all_questions}
        selected_questions = [
            questions_map[qid] for qid in selected_question_ids if qid in questions_map
        ]
        if len(selected_questions) != 5:
            selected_questions = random.sample(all_questions, 5)
            selected_question_ids = [q["id"] for q in selected_questions]
            session[session_key] = selected_question_ids
    started_at_epoch = int(quiz["started_at"].timestamp())

    if request.method == "POST":
        elapsed_seconds = int(time.time()) - started_at_epoch
        allowed_seconds = int(quiz.get("duration_minutes") or 10) * 60
        timed_out = elapsed_seconds >= allowed_seconds

        correct_count = 0
        for q in selected_questions:
            selected = request.form.get(f"question_{q['id']}", "").strip().upper()
            if selected == q["correct_option"]:
                correct_count += 1

        execute_query(
            """
            INSERT INTO quiz_attempts (quiz_id, student_id, score, total_questions)
            VALUES (%s, %s, %s, %s)
            """,
            (quiz_id, user_id, correct_count, len(selected_questions)),
        )

        session.pop(session_key, None)
        execute_query(
            "DELETE FROM quiz_waiting WHERE quiz_id=%s AND student_id=%s",
            (quiz_id, user_id),
        )
        marks_out_of_5 = round((correct_count / max(len(selected_questions), 1)) * 5, 2)
        if timed_out:
            flash(f"Time is over. Quiz auto-submitted. You scored {marks_out_of_5}/5", "warning")
        else:
            flash(f"Quiz submitted. You scored {marks_out_of_5}/5", "success")
        return redirect(url_for("student_dashboard"))

    return render_template(
        "attempt_quiz.html",
        quiz=quiz,
        questions=selected_questions,
        duration_seconds=int(quiz.get("duration_minutes") or 10) * 60,
        start_time=started_at_epoch,
        server_now=int(time.time()),
    )


@app.route("/admin")
@login_required(role="admin")
def admin_dashboard():
    admin_id = session["user_id"]
    assignments = fetch_all(
        "SELECT sem, section, subject_code FROM admin_subject_assignments WHERE admin_id=%s ORDER BY sem, section, subject_code",
        (admin_id,),
    )

    filter_mapping = request.args.get("mapping", "").strip()
    filter_sem = request.args.get("sem", "").strip()
    filter_section = request.args.get("section", "").strip().upper()
    filter_subject = request.args.get("subject_code", "").strip().upper()
    if filter_mapping and (not filter_sem or not filter_section or not filter_subject):
        parts = filter_mapping.split("|")
        if len(parts) == 3:
            filter_sem, filter_section, filter_subject = parts[0], parts[1].upper(), parts[2].upper()
    if (not filter_mapping) and filter_sem and filter_section and filter_subject:
        filter_mapping = f"{filter_sem}|{filter_section}|{filter_subject}"
    where_sql = "q.admin_id=%s"
    params = [admin_id]
    if filter_sem:
        where_sql += " AND q.sem=%s"
        params.append(int(filter_sem))
    if filter_section:
        where_sql += " AND q.section=%s"
        params.append(filter_section)
    if filter_subject:
        where_sql += " AND q.subject_code=%s"
        params.append(filter_subject)

    quizzes = fetch_all(
        f"""
        SELECT q.id, q.title, q.quiz_date, q.sem, q.section, q.batch, q.subject_code, q.enabled, q.duration_minutes, q.started_at,
               (SELECT COUNT(*) FROM quiz_waiting qw WHERE qw.quiz_id=q.id) AS waiting_count,
               (SELECT COUNT(*) FROM quiz_attempts qa WHERE qa.quiz_id=q.id) AS attempt_count,
               CASE
                   WHEN q.started_at IS NULL AND q.quiz_date < CURDATE()
                        AND (SELECT COUNT(*) FROM quiz_attempts qa WHERE qa.quiz_id=q.id) = 0 THEN 'EXPIRED'
                   WHEN q.started_at IS NULL THEN 'NOT_STARTED'
                   WHEN (SELECT COUNT(*) FROM quiz_waiting qw WHERE qw.quiz_id=q.id) = 0
                        AND (SELECT COUNT(*) FROM quiz_attempts qa WHERE qa.quiz_id=q.id) > 0 THEN 'COMPLETED'
                   ELSE 'STARTED'
               END AS quiz_status,
               COUNT(qq.id) AS question_count
        FROM quizzes q
        LEFT JOIN quiz_questions qq ON qq.quiz_id=q.id
        WHERE {where_sql}
        GROUP BY q.id
        ORDER BY q.quiz_date DESC, q.created_at DESC
        """,
        tuple(params),
    )

    marks = fetch_all(
        f"""
        SELECT
            u.id AS student_id,
            u.username,
            u.full_name,
            u.batch AS student_batch,
            q.id AS quiz_id,
            q.quiz_date, q.subject_code, q.batch AS quiz_batch,
            ROUND((qa.score / NULLIF(qa.total_questions, 0)) * 5, 2) AS marks_out_of_5
        FROM quiz_attempts qa
        JOIN users u ON u.id=qa.student_id
        JOIN quizzes q ON q.id=qa.quiz_id
        WHERE {where_sql}
        ORDER BY u.username ASC, q.quiz_date ASC
        """,
        tuple(params),
    )

    student_map = {}
    for row in marks:
        student_map[row["student_id"]] = {
            "student_id": row["student_id"],
            "username": row["username"],
            "full_name": row.get("full_name"),
            "batch": row.get("student_batch"),
        }
    students = sorted(student_map.values(), key=lambda s: (s["username"] or "").upper())

    quiz_columns = []
    conducted_quiz_ids = set()
    for q in sorted(quizzes, key=lambda quiz: (quiz["quiz_date"], quiz["id"])):
        q_id = str(q["id"])
        quiz_columns.append(
            {
                "quiz_id": q_id,
                "label": f"{q['quiz_date']} - {q.get('batch') or '-'} - {q['title']}",
                "batch": q.get("batch"),
            }
        )
        if str(q["quiz_date"]) <= str(date.today()):
            conducted_quiz_ids.add(q_id)

    marks_lookup = {}
    for row in marks:
        q_id = str(row["quiz_id"])
        if q_id in conducted_quiz_ids:
            key = (row["student_id"], q_id)
            marks_lookup[key] = row["marks_out_of_5"]

    marks_matrix = []
    for student in students:
        row = {
            "username": student["username"],
            "full_name": student.get("full_name"),
            "batch": student.get("batch"),
            "date_marks": {},
        }
        sum_marks = 0.0
        eligible_conducted = 0
        for column in quiz_columns:
            quiz_id = column["quiz_id"]
            is_eligible = (column.get("batch") is None) or (column.get("batch") == student.get("batch"))
            if quiz_id in conducted_quiz_ids and is_eligible:
                row["date_marks"][quiz_id] = marks_lookup.get((student["student_id"], quiz_id))
                if row["date_marks"][quiz_id] is not None:
                    sum_marks += float(row["date_marks"][quiz_id])
                eligible_conducted += 1
            else:
                row["date_marks"][quiz_id] = None
        row["avg_out_of_10"] = round((sum_marks / eligible_conducted / 5) * 10, 2) if eligible_conducted > 0 else None
        marks_matrix.append(row)

    return render_template(
        "admin_dashboard.html",
        quizzes=quizzes,
        quiz_columns=quiz_columns,
        marks_matrix=marks_matrix,
        assignments=assignments,
        filter_sem=filter_sem,
        filter_section=filter_section,
        filter_subject=filter_subject,
        filter_mapping=filter_mapping,
    )


@app.route("/admin/quiz/<int:quiz_id>/start", methods=["POST"])
@login_required(role="admin")
def start_quiz(quiz_id):
    quiz = fetch_one("SELECT id, started_at, enabled, admin_id FROM quizzes WHERE id=%s", (quiz_id,))
    if not quiz:
        flash("Quiz not found.", "warning")
        return redirect(url_for("admin_dashboard"))
    if int(quiz["admin_id"]) != int(session["user_id"]):
        flash("Unauthorized quiz access.", "danger")
        return redirect(url_for("admin_dashboard"))
    if quiz["enabled"] != 1:
        flash("Enable quiz before starting.", "warning")
        return redirect(url_for("admin_dashboard"))
    if quiz.get("started_at"):
        flash("Quiz is already started.", "info")
        return redirect(url_for("admin_dashboard"))

    execute_query("UPDATE quizzes SET started_at=NOW() WHERE id=%s", (quiz_id,))
    flash("Quiz started successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/waiting-counts")
@login_required(role="admin")
def admin_waiting_counts():
    admin_id = session["user_id"]
    filter_sem = request.args.get("sem", "").strip()
    filter_section = request.args.get("section", "").strip().upper()
    filter_subject = request.args.get("subject_code", "").strip().upper()
    where_sql = "q.admin_id=%s"
    params = [admin_id]
    if filter_sem:
        where_sql += " AND q.sem=%s"
        params.append(int(filter_sem))
    if filter_section:
        where_sql += " AND q.section=%s"
        params.append(filter_section)
    if filter_subject:
        where_sql += " AND q.subject_code=%s"
        params.append(filter_subject)
    rows = fetch_all(
        f"""
        SELECT q.id AS quiz_id,
               (SELECT COUNT(*) FROM quiz_waiting qw WHERE qw.quiz_id=q.id) AS waiting_count,
               (SELECT COUNT(*) FROM quiz_attempts qa WHERE qa.quiz_id=q.id) AS attempt_count,
               CASE
                   WHEN q.started_at IS NULL AND q.quiz_date < CURDATE()
                        AND (SELECT COUNT(*) FROM quiz_attempts qa WHERE qa.quiz_id=q.id) = 0 THEN 'EXPIRED'
                   WHEN q.started_at IS NULL THEN 'NOT_STARTED'
                   WHEN (SELECT COUNT(*) FROM quiz_waiting qw WHERE qw.quiz_id=q.id) = 0
                        AND (SELECT COUNT(*) FROM quiz_attempts qa WHERE qa.quiz_id=q.id) > 0 THEN 'COMPLETED'
                   ELSE 'STARTED'
               END AS quiz_status
        FROM quizzes q
        WHERE {where_sql}
        """,
        tuple(params),
    )
    payload = {
        str(row["quiz_id"]): {
            "waiting_count": row["waiting_count"],
            "attempt_count": row["attempt_count"],
            "quiz_status": row["quiz_status"],
        }
        for row in rows
    }
    return jsonify(payload)


@app.route("/admin/marks/export")
@login_required(role="admin")
def export_admin_marks():
    admin_id = session["user_id"]
    quizzes = fetch_all(
        """
        SELECT q.id, q.quiz_date, q.title, q.sem, q.section, q.batch, q.subject_code
        FROM quizzes q
        WHERE q.admin_id=%s
        ORDER BY q.quiz_date ASC, q.id ASC
        """,
        (admin_id,),
    )
    quiz_columns = [
        {
            "quiz_id": str(q["id"]),
            "quiz_date": str(q["quiz_date"]),
            "batch": q.get("batch"),
            "label": f"{q['quiz_date']} - S{q['sem']}{q['section']} - {q.get('batch') or '-'} - {q['subject_code']} - {q['title']}",
        }
        for q in quizzes
    ]

    marks = fetch_all(
        """
        SELECT
            u.id AS student_id,
            u.username,
            u.full_name,
            u.batch AS student_batch,
            q.id AS quiz_id,
            q.quiz_date,
            q.batch AS quiz_batch,
            ROUND((qa.score / NULLIF(qa.total_questions, 0)) * 5, 2) AS marks_out_of_5
        FROM quiz_attempts qa
        JOIN users u ON u.id=qa.student_id
        JOIN quizzes q ON q.id=qa.quiz_id
        WHERE q.admin_id=%s
        ORDER BY u.username ASC, q.quiz_date ASC
        """,
        (admin_id,),
    )

    student_map = {}
    for row in marks:
        student_map[row["student_id"]] = {
            "student_id": row["student_id"],
            "username": row["username"],
            "full_name": row.get("full_name"),
            "batch": row.get("student_batch"),
        }
    students = sorted(student_map.values(), key=lambda s: s["username"])

    conducted_quiz_ids = {column["quiz_id"] for column in quiz_columns if column["quiz_date"] <= str(date.today())}

    marks_lookup = {}
    for row in marks:
        q_id = str(row["quiz_id"])
        if q_id in conducted_quiz_ids:
            marks_lookup[(row["student_id"], q_id)] = row["marks_out_of_5"]

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Student Marks"

    headers = ["Student", "Name"] + [f"{c['label']} (Marks)" for c in quiz_columns] + ["Running Avg (out of 10)"]
    sheet.append(headers)

    for student in students:
        row_values = [student["username"], student.get("full_name") or ""]
        sum_marks = 0.0
        eligible_conducted = 0
        for column in quiz_columns:
            quiz_id = column["quiz_id"]
            is_eligible = (column.get("batch") is None) or (column.get("batch") == student.get("batch"))
            if column["quiz_id"] in conducted_quiz_ids and is_eligible:
                eligible_conducted += 1
                mark = marks_lookup.get((student["student_id"], quiz_id))
                row_values.append(mark if mark is not None else "-")
                if mark is not None:
                    sum_marks += float(mark)
            else:
                row_values.append("-")

        avg_out_of_10 = round((sum_marks / eligible_conducted / 5) * 10, 2) if eligible_conducted > 0 else None
        row_values.append(avg_out_of_10 if avg_out_of_10 is not None else "N/A")
        sheet.append(row_values)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="student_marks_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/admin/quiz/upload", methods=["GET", "POST"])
@login_required(role="admin")
def upload_quiz():
    admin_id = session["user_id"]
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        quiz_date = request.form.get("quiz_date", "").strip()
        sem = request.form.get("sem", "").strip()
        section = request.form.get("section", "").strip().upper()
        batch = request.form.get("batch", "").strip().upper()
        subject_code = request.form.get("subject_code", "").strip().upper()
        assignment_raw = request.form.get("assignment", "").strip()
        if assignment_raw and (not sem or not section or not subject_code):
            parts = assignment_raw.split("|")
            if len(parts) == 3:
                sem, section, subject_code = parts[0], parts[1].upper(), parts[2].upper()
        enabled = 1 if request.form.get("enabled") == "on" else 0
        duration_minutes = int(request.form.get("duration_minutes", "10"))
        file = request.files.get("quiz_csv")

        if not title or not quiz_date or not sem or not section or not batch or not subject_code or not file or duration_minutes <= 0:
            flash("Title, sem, section, batch, subject, date, duration and CSV file are required.", "danger")
            return redirect(url_for("upload_quiz"))
        if not sem.isdigit() or int(sem) < 1 or int(sem) > 8:
            flash("Semester must be between 1 and 8.", "danger")
            return redirect(url_for("upload_quiz"))
        if not re.fullmatch(r"[A-Z]{3,4}", subject_code):
            flash("Subject code must be 3-4 uppercase letters.", "danger")
            return redirect(url_for("upload_quiz"))
        if not valid_batch_for_section(section, batch):
            flash("Batch must match section (e.g. A1/A2/A3 for section A).", "danger")
            return redirect(url_for("upload_quiz"))
        assignment = fetch_one(
            """
            SELECT id FROM admin_subject_assignments
            WHERE admin_id=%s AND sem=%s AND section=%s AND subject_code=%s
            """,
            (admin_id, int(sem), section, subject_code),
        )
        if not assignment:
            flash("You are not assigned to this sem/section/subject combination.", "danger")
            return redirect(url_for("upload_quiz"))

        quiz_id = execute_query(
            """
            INSERT INTO quizzes (admin_id, title, quiz_date, sem, section, batch, subject_code, enabled, duration_minutes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (admin_id, title, quiz_date, int(sem), section, batch, subject_code, enabled, duration_minutes),
        )

        try:
            stream = io.StringIO(file.stream.read().decode("utf-8"), newline=None)
            reader = csv.reader(stream)
            rows_to_insert = []

            for row_num, row in enumerate(reader, start=1):
                if len(row) != 6:
                    raise ValueError(
                        f"Invalid format at row {row_num}. Expected 6 columns, got {len(row)}."
                    )

                question, option_a, option_b, option_c, option_d, correct_option = [
                    cell.strip() for cell in row
                ]
                correct_option = correct_option.upper()

                if correct_option not in {"A", "B", "C", "D"}:
                    raise ValueError(
                        f"Invalid correct option at row {row_num}. Use A/B/C/D."
                    )

                rows_to_insert.append(
                    (
                        quiz_id,
                        question,
                        option_a,
                        option_b,
                        option_c,
                        option_d,
                        correct_option,
                    )
                )

            if len(rows_to_insert) < 5:
                raise ValueError("A quiz must have at least 5 questions.")
            if len(rows_to_insert) > 20:
                raise ValueError("A quiz can have a maximum of 20 questions.")

            execute_query(
                """
                INSERT INTO quiz_questions
                (quiz_id, question, option_a, option_b, option_c, option_d, correct_option)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                rows_to_insert,
                many=True,
            )
            flash("Quiz uploaded successfully.", "success")
            return redirect(url_for("admin_dashboard"))

        except Exception as exc:
            execute_query("DELETE FROM quizzes WHERE id=%s", (quiz_id,))
            flash(f"Upload failed: {exc}", "danger")
            return redirect(url_for("upload_quiz"))

    assignments = fetch_all(
        "SELECT sem, section, subject_code FROM admin_subject_assignments WHERE admin_id=%s ORDER BY sem, section, subject_code",
        (admin_id,),
    )
    return render_template("upload_quiz.html", assignments=assignments)


@app.route("/admin/assignment/add", methods=["POST"])
@login_required(role="admin")
def add_admin_assignment():
    admin_id = session["user_id"]
    sem = request.form.get("sem", "").strip()
    section = request.form.get("section", "").strip().upper()
    subject_code = request.form.get("subject_code", "").strip().upper()
    if not sem or not section or not subject_code:
        flash("Sem, section and subject are required.", "danger")
        return redirect(url_for("admin_dashboard"))
    if not sem.isdigit() or int(sem) < 1 or int(sem) > 8:
        flash("Semester must be between 1 and 8.", "danger")
        return redirect(url_for("admin_dashboard"))
    if not re.fullmatch(r"[A-Z]", section):
        flash("Section must be A-Z.", "danger")
        return redirect(url_for("admin_dashboard"))
    if not re.fullmatch(r"[A-Z]{3,4}", subject_code):
        flash("Subject code must be 3-4 uppercase letters.", "danger")
        return redirect(url_for("admin_dashboard"))
    execute_query(
        """
        INSERT INTO admin_subject_assignments (admin_id, sem, section, subject_code)
        VALUES (%s, %s, %s, %s)
        """,
        (admin_id, int(sem), section, subject_code),
    )
    flash("Subject assignment added.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/quiz/<int:quiz_id>/toggle", methods=["POST"])
@login_required(role="admin")
def toggle_quiz(quiz_id):
    quiz = fetch_one("SELECT id, enabled, admin_id FROM quizzes WHERE id=%s", (quiz_id,))
    if not quiz:
        flash("Quiz not found.", "warning")
        return redirect(url_for("admin_dashboard"))
    if int(quiz["admin_id"]) != int(session["user_id"]):
        flash("Unauthorized quiz access.", "danger")
        return redirect(url_for("admin_dashboard"))

    new_status = 0 if quiz["enabled"] == 1 else 1
    execute_query("UPDATE quizzes SET enabled=%s WHERE id=%s", (new_status, quiz_id))
    flash("Quiz status updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/cleanup", methods=["POST"])
@login_required(role="admin")
def admin_cleanup():
    admin_id = session["user_id"]
    sem = request.form.get("sem", "").strip()
    section = request.form.get("section", "").strip().upper()
    subject_code = request.form.get("subject_code", "").strip().upper()
    quizzes = fetch_all(
        """
        SELECT q.id, q.quiz_date, q.title
        FROM quizzes q
        WHERE q.admin_id=%s AND q.sem=%s AND q.section=%s AND q.subject_code=%s
        ORDER BY q.quiz_date ASC
        """,
        (admin_id, int(sem), section, subject_code),
    )
    if not quizzes:
        flash("No data found for selected sem/section/subject.", "warning")
        return redirect(url_for("admin_dashboard"))

    quiz_ids = [q["id"] for q in quizzes]
    in_clause = ",".join(["%s"] * len(quiz_ids))
    marks = fetch_all(
        f"""
        SELECT u.username, u.full_name, q.id AS quiz_id,
               ROUND((qa.score / NULLIF(qa.total_questions, 0)) * 5, 2) AS marks_out_of_5
        FROM quiz_attempts qa
        JOIN users u ON u.id=qa.student_id
        JOIN quizzes q ON q.id=qa.quiz_id
        WHERE qa.quiz_id IN ({in_clause})
        """,
        tuple(quiz_ids),
    )
    students = fetch_all("SELECT id, username, full_name FROM users WHERE role='student' ORDER BY username")
    lookup = {(m["username"], m["quiz_id"]): m["marks_out_of_5"] for m in marks}
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Final Sheet"
    headers = ["USN", "Name"] + [f"{q['quiz_date']} - {q['title']}" for q in quizzes] + ["Avg Out of 10"]
    sheet.append(headers)
    for s in students:
        row = [s["username"], s["full_name"]]
        total = 0.0
        for q in quizzes:
            mark = lookup.get((s["username"], q["id"]))
            row.append(mark if mark is not None else "-")
            if mark is not None:
                total += float(mark)
        avg = round((total / max(len(quizzes), 1) / 5) * 10, 2)
        row.append(avg)
        sheet.append(row)

    execute_query(
        "DELETE FROM quizzes WHERE admin_id=%s AND sem=%s AND section=%s AND subject_code=%s",
        (admin_id, int(sem), section, subject_code),
    )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"final_sheet_sem{sem}_{section}_{subject_code}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(debug=True)
