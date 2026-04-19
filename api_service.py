import os
import sqlite3
import pickle
import base64
from flask import Flask, request, send_file

app = Flask(__name__)

# 1. CRITICAL: Hardcoded Cloud Credentials
# Боти обожнюють шукати такі формати ключів
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
DB_ROOT_PASSWORD = "root_password_123_do_not_share"

@app.route('/ping', methods=['GET'])
def ping_server():
    """Перевірка доступності сервера."""
    # 2. CRITICAL: OS Command Injection (RCE)
    # Зловмисник може передати: ip="8.8.8.8; rm -rf /"
    target = request.args.get('ip')
    os.system(f"ping -c 1 {target}")
    return "Ping executed!"

@app.route('/user_data', methods=['POST'])
def load_user_data():
    """Завантаження профілю користувача."""
    # 3. CRITICAL: Insecure Deserialization (Pickle)
    # Зловмисник може згенерувати payload, який виконає довільний код при десеріалізації
    data = request.form.get('payload')
    decoded = base64.b64decode(data)
    user_obj = pickle.loads(decoded)
    return f"Loaded user state: {user_obj}"

@app.route('/download', methods=['GET'])
def download_file():
    """Завантаження файлів користувача."""
    # 4. CRITICAL: Path Traversal (Directory Traversal)
    # Зловмисник може передати: file="../../../../../etc/passwd"
    filename = request.args.get('file')
    return send_file(f"/var/www/uploads/{filename}")

@app.route('/login', methods=['POST'])
def login():
    """Аутентифікація."""
    # 5. CRITICAL: Raw SQL Injection у чистому вигляді
    username = request.form.get('user')
    password = request.form.get('pass')
    
    conn = sqlite3.connect('production_users.db')
    cursor = conn.cursor()
    
    # Зловмисник вводить user: "admin' --" і заходить без пароля
    cursor.execute(f"SELECT id, role FROM users WHERE username='{username}' AND password='{password}'")
    user = cursor.fetchone()
    
    if user:
        return f"Welcome back, {user[0]}"
    return "Access Denied", 401

if __name__ == '__main__':
    # Запуск на всіх інтерфейсах з правами, які дозволяють все
    app.run(host='0.0.0.0', port=80)