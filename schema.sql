CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    faculty_code VARCHAR(50) UNIQUE NULL,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('super_admin', 'admin', 'student') NOT NULL,
    sem TINYINT NULL,
    section VARCHAR(5) NULL,
    batch VARCHAR(5) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quizzes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    admin_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    quiz_date DATE NOT NULL,
    sem TINYINT NOT NULL,
    section VARCHAR(5) NOT NULL,
    batch VARCHAR(5) NULL,
    subject_code VARCHAR(10) NOT NULL,
    enabled TINYINT(1) DEFAULT 0,
    duration_minutes INT NOT NULL DEFAULT 10,
    started_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    quiz_id INT NOT NULL,
    question TEXT NOT NULL,
    option_a VARCHAR(255) NOT NULL,
    option_b VARCHAR(255) NOT NULL,
    option_c VARCHAR(255) NOT NULL,
    option_d VARCHAR(255) NOT NULL,
    correct_option ENUM('A', 'B', 'C', 'D') NOT NULL,
    FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    quiz_id INT NOT NULL,
    student_id INT NOT NULL,
    score INT NOT NULL,
    total_questions INT NOT NULL,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_quiz_student (quiz_id, student_id),
    FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

<<<<<<< HEAD
=======
CREATE TABLE IF NOT EXISTS quiz_attempt_answers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id INT NOT NULL,
    question_id INT NOT NULL,
    selected_option ENUM('A', 'B', 'C', 'D') NULL,
    is_correct TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_attempt_question (attempt_id, question_id),
    FOREIGN KEY (attempt_id) REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES quiz_questions(id) ON DELETE CASCADE
);

>>>>>>> 7db182e7247ad270679c528418a8495a7b8e3fba
CREATE TABLE IF NOT EXISTS quiz_waiting (
    id INT AUTO_INCREMENT PRIMARY KEY,
    quiz_id INT NOT NULL,
    student_id INT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_waiting_quiz_student (quiz_id, student_id),
    FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

<<<<<<< HEAD
=======
CREATE TABLE IF NOT EXISTS record_book_marks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    quiz_id INT NOT NULL,
    student_id INT NOT NULL,
    marks_out_of_10 DECIMAL(5,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_record_book_quiz_student (quiz_id, student_id),
    FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

>>>>>>> 7db182e7247ad270679c528418a8495a7b8e3fba
CREATE TABLE IF NOT EXISTS admin_subject_assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    admin_id INT NOT NULL,
    sem TINYINT NOT NULL,
    section VARCHAR(5) NOT NULL,
    subject_code VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_admin_subject (admin_id, sem, section, subject_code),
    FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE CASCADE
);

INSERT INTO users (username, faculty_code, full_name, email, password, role, sem, section, batch)
VALUES
    ('admin1', 'FAC001', 'Admin User', 'admin1@example.com', 'scrypt:32768:8:1$WZlLWauOy4aRwLLe$bcfb273c8f1270e1d1ec1072dd4b783f3caf6bbaec3864d4ad79f2b443dd8650d17539a33d97e56c6a325b74893029effc71b8ec3571c72c5123040777366a46', 'admin', NULL, NULL, NULL),
    ('student1', NULL, 'Student One', NULL, 'scrypt:32768:8:1$1XiQd0cLqNAk3nbJ$52c7efccfe983023ef5bdd3c0456f60b01b2bc74f88e59d8cd34ffb7a12124cae7d69d63e4869e229f41e4e5fb69077fae4f1be3d1dee67587affc1cacc01118', 'student', 5, 'A', 'A1'),
    ('student2', NULL, 'Student Two', NULL, 'scrypt:32768:8:1$1XiQd0cLqNAk3nbJ$52c7efccfe983023ef5bdd3c0456f60b01b2bc74f88e59d8cd34ffb7a12124cae7d69d63e4869e229f41e4e5fb69077fae4f1be3d1dee67587affc1cacc01118', 'student', 5, 'A', 'A2')
ON DUPLICATE KEY UPDATE username = VALUES(username);
