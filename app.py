import csv
import io
import os
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

from db import execute_query, fetch_all, fetch_one

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-me")


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
            "SELECT id, username, role FROM users WHERE username=%s AND password=%s",
            (username, password),
        )

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "danger")

    return render_template("login.html")


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
        SELECT u.username, q.title, q.quiz_date,
               ROUND((qa.score / NULLIF(qa.total_questions, 0)) * 5, 2) AS marks_out_of_5,
               ra.avg_out_of_10
        FROM quiz_attempts qa
        JOIN users u ON u.id=qa.student_id
        JOIN quizzes q ON q.id=qa.quiz_id
        LEFT JOIN (
            SELECT student_id,
                   ROUND((AVG(score / NULLIF(total_questions, 0) * 5) / 5) * 10, 2) AS avg_out_of_10
            FROM quiz_attempts
            GROUP BY student_id
        ) ra ON ra.student_id=u.id
        ORDER BY q.quiz_date DESC, u.username ASC
        """
    )

    return render_template("admin_dashboard.html", quizzes=quizzes, marks=marks)


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
