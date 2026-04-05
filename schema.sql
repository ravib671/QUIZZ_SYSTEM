CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('admin', 'student') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quizzes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    quiz_date DATE NOT NULL,
    enabled TINYINT(1) DEFAULT 0,
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

INSERT INTO users (username, full_name, password, role)
VALUES
    ('admin1', 'Admin User', 'scrypt:32768:8:1$WZlLWauOy4aRwLLe$bcfb273c8f1270e1d1ec1072dd4b783f3caf6bbaec3864d4ad79f2b443dd8650d17539a33d97e56c6a325b74893029effc71b8ec3571c72c5123040777366a46', 'admin'),
    ('student1', 'Student One', 'scrypt:32768:8:1$1XiQd0cLqNAk3nbJ$52c7efccfe983023ef5bdd3c0456f60b01b2bc74f88e59d8cd34ffb7a12124cae7d69d63e4869e229f41e4e5fb69077fae4f1be3d1dee67587affc1cacc01118', 'student'),
    ('student2', 'Student Two', 'scrypt:32768:8:1$1XiQd0cLqNAk3nbJ$52c7efccfe983023ef5bdd3c0456f60b01b2bc74f88e59d8cd34ffb7a12124cae7d69d63e4869e229f41e4e5fb69077fae4f1be3d1dee67587affc1cacc01118', 'student')
ON DUPLICATE KEY UPDATE username = VALUES(username);
