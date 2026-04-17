import os
import mysql.connector


def get_db_connection():
    return mysql.connector.connect(
        host="127.0.0.1",   # avoid localhost issues
        port=3306,
        user="root",
        password="",        # 🔥 force empty password
        database="quizz_system",
    )


def fetch_all(query, params=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def fetch_one(query, params=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def execute_query(query, params=None, many=False):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if many:
            cursor.executemany(query, params)
        else:
            cursor.execute(query, params or ())
        conn.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        conn.close()
