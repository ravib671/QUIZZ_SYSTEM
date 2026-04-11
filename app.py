import csv
import io
import os
import re
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from db import execute_query, fetch_all, fetch_one

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-me")


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
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not usn or not full_name or not password or not confirm_password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        if not re.fullmatch(r"[A-Z0-9]{6,20}", usn):
            flash("USN must be 6-20 characters (A-Z, 0-9 only).", "danger")
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
            "INSERT INTO users (username, full_name, password, role) VALUES (%s, %s, %s, 'student')",
            (usn, full_name, hashed_password),
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
    return redirect(url_for("student_dashboard"))


@app.route("/student")
@login_required(role="student")
def student_dashboard():
    user_id = session["user_id"]

    available_quizzes = fetch_all(
        """
        SELECT q.id, q.title, q.quiz_date,
               CASE WHEN qa.id IS NULL THEN 0 ELSE 1 END AS attempted
        FROM quizzes q
        LEFT JOIN quiz_attempts qa ON qa.quiz_id=q.id AND qa.student_id=%s
        WHERE q.enabled=1
        ORDER BY q.quiz_date DESC
        """,
        (user_id,),
    )

    history = fetch_all(
        """
        SELECT q.title, q.quiz_date, qa.score, qa.total_questions,
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
        SELECT ROUND((AVG(qa.score / NULLIF(qa.total_questions, 0) * 5) / 5) * 10, 2) AS avg_out_of_10
        FROM quiz_attempts qa
        WHERE qa.student_id=%s
        """,
        (user_id,),
    )

    return render_template(
        "student_dashboard.html",
        available_quizzes=available_quizzes,
        history=history,
        avg_out_of_10=running_avg["avg_out_of_10"] if running_avg else None,
    )


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


@app.route("/student/quiz/<int:quiz_id>", methods=["GET", "POST"])
@login_required(role="student")
def attempt_quiz(quiz_id):
    user_id = session["user_id"]

    quiz = fetch_one("SELECT id, title, enabled FROM quizzes WHERE id=%s", (quiz_id,))
    if not quiz or quiz["enabled"] != 1:
        flash("Quiz is not available.", "warning")
        return redirect(url_for("student_dashboard"))

    already_attempted = fetch_one(
        "SELECT id FROM quiz_attempts WHERE quiz_id=%s AND student_id=%s",
        (quiz_id, user_id),
    )
    if already_attempted:
        flash("You already attempted this quiz.", "info")
        return redirect(url_for("student_dashboard"))

    questions = fetch_all(
        """
        SELECT id, question, option_a, option_b, option_c, option_d, correct_option
        FROM quiz_questions
        WHERE quiz_id=%s
        ORDER BY id ASC
        """,
        (quiz_id,),
    )

    if request.method == "POST":
        correct_count = 0
        for q in questions:
            selected = request.form.get(f"question_{q['id']}", "").strip().upper()
            if selected == q["correct_option"]:
                correct_count += 1

        execute_query(
            """
            INSERT INTO quiz_attempts (quiz_id, student_id, score, total_questions)
            VALUES (%s, %s, %s, %s)
            """,
            (quiz_id, user_id, correct_count, len(questions)),
        )

        marks_out_of_5 = round((correct_count / max(len(questions), 1)) * 5, 2)
        flash(f"Quiz submitted. You scored {marks_out_of_5}/5", "success")
        return redirect(url_for("student_dashboard"))

    return render_template("attempt_quiz.html", quiz=quiz, questions=questions)


@app.route("/admin")
@login_required(role="admin")
def admin_dashboard():
    quizzes = fetch_all(
        """
        SELECT q.id, q.title, q.quiz_date, q.enabled, COUNT(qq.id) AS question_count
        FROM quizzes q
        LEFT JOIN quiz_questions qq ON qq.quiz_id=q.id
        GROUP BY q.id
        ORDER BY q.quiz_date DESC, q.created_at DESC
        """
    )

    marks = fetch_all(
        """
        SELECT
            u.id AS student_id,
            u.username,
            q.quiz_date,
            ROUND((qa.score / NULLIF(qa.total_questions, 0)) * 5, 2) AS marks_out_of_5
        FROM quiz_attempts qa
        JOIN users u ON u.id=qa.student_id
        JOIN quizzes q ON q.id=qa.quiz_id
        ORDER BY u.username ASC, q.quiz_date ASC
        """
    )

    students = fetch_all(
        """
        SELECT
            u.id AS student_id,
            u.username,
            ROUND((AVG(qa.score / NULLIF(qa.total_questions, 0) * 5) / 5) * 10, 2) AS avg_out_of_10
        FROM users u
        LEFT JOIN quiz_attempts qa ON qa.student_id=u.id
        WHERE LOWER(u.role)='student'
        GROUP BY u.id, u.username
        ORDER BY u.username ASC
        """
    )

    quiz_dates = [str(q["quiz_date"]) for q in sorted(quizzes, key=lambda q: q["quiz_date"])]

    marks_lookup = {}
    for row in marks:
        key = (row["student_id"], str(row["quiz_date"]))
        marks_lookup[key] = row["marks_out_of_5"]

    marks_matrix = []
    for student in students:
        row = {
            "username": student["username"],
            "avg_out_of_10": student["avg_out_of_10"],
            "date_marks": {},
        }
        for date_key in quiz_dates:
            row["date_marks"][date_key] = marks_lookup.get((student["student_id"], date_key))
        marks_matrix.append(row)

    # Fallback for legacy data where user role values may be inconsistent
    # but attempts already exist.
    if not marks_matrix and marks:
        fallback_students = {}
        for row in marks:
            fallback_students[row["student_id"]] = row["username"]

        for student_id, username in sorted(fallback_students.items(), key=lambda s: s[1]):
            student_marks = [
                m["marks_out_of_5"] for m in marks if m["student_id"] == student_id
            ]
            avg_out_of_10 = None
            if student_marks:
                avg_out_of_10 = round((sum(student_marks) / len(student_marks) / 5) * 10, 2)

            row = {"username": username, "avg_out_of_10": avg_out_of_10, "date_marks": {}}
            for date_key in quiz_dates:
                row["date_marks"][date_key] = marks_lookup.get((student_id, date_key))
            marks_matrix.append(row)

    return render_template(
        "admin_dashboard.html",
        quizzes=quizzes,
        quiz_dates=quiz_dates,
        marks_matrix=marks_matrix,
    )


@app.route("/admin/quiz/upload", methods=["GET", "POST"])
@login_required(role="admin")
def upload_quiz():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        quiz_date = request.form.get("quiz_date", "").strip()
        enabled = 1 if request.form.get("enabled") == "on" else 0
        file = request.files.get("quiz_csv")

        if not title or not quiz_date or not file:
            flash("Title, date and CSV file are required.", "danger")
            return redirect(url_for("upload_quiz"))

        quiz_id = execute_query(
            "INSERT INTO quizzes (title, quiz_date, enabled) VALUES (%s, %s, %s)",
            (title, quiz_date, enabled),
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

    return render_template("upload_quiz.html")


@app.route("/admin/quiz/<int:quiz_id>/toggle", methods=["POST"])
@login_required(role="admin")
def toggle_quiz(quiz_id):
    quiz = fetch_one("SELECT id, enabled FROM quizzes WHERE id=%s", (quiz_id,))
    if not quiz:
        flash("Quiz not found.", "warning")
        return redirect(url_for("admin_dashboard"))

    new_status = 0 if quiz["enabled"] == 1 else 1
    execute_query("UPDATE quizzes SET enabled=%s WHERE id=%s", (new_status, quiz_id))
    flash("Quiz status updated.", "success")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
