import sqlite3
import os

# 1. CRITICAL: Hardcoded Secret 
AWS_SECRET_KEY = "AKIAIOSFODNN7EXAMPLE_SECRET_DO_NOT_COMMIT"
ADMIN_PASSWORD = "super_secret_admin_123"

def get_user_profile(username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # 2. CRITICAL: SQL Injection (SQL-ін'єкція)
    query = f"SELECT * FROM users WHERE username = '{username}' AND role = 'user';"
    cursor.execute(query)
    
    user = cursor.fetchone()
    conn.close()
    return user

def process_math_expression(user_input):
    """Калькулятор, який виконує математичні вирази від юзера."""
    # 3. CRITICAL: Remote Code Execution (RCE) через eval()
    print(f"Calculating: {user_input}")
    result = eval(user_input)
    return result

if __name__ == "__main__":
    print("User profile:", get_user_profile("admin' --")) 
    print("Calculation:", process_math_expression("2 + 2"))