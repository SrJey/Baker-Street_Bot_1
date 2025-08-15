import os
import psycopg2
from datetime import date, datetime

# Получаем URL для подключения к БД из переменных окружения
DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    """Устанавливает соединение с базой данных."""
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Инициализирует таблицы в базе данных, если они не существуют."""
    conn = get_db_connection()
    cur = conn.cursor()
    # Таблица сотрудников
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            code VARCHAR(50) UNIQUE NOT NULL
        );
    """)
    # Таблица для учета выданных талонов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,
            issue_date DATE NOT NULL,
            issue_time TIME NOT NULL
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def get_all_employees():
    """Возвращает список всех сотрудников."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, code FROM employees ORDER BY name;")
    employees = cur.fetchall()
    cur.close()
    conn.close()
    return employees

def add_employee(name, code):
    """Добавляет нового сотрудника в базу данных."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO employees (name, code) VALUES (%s, %s);", (name, code))
    conn.commit()
    cur.close()
    conn.close()

def remove_employee(employee_id):
    """Удаляет сотрудника по его ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM employees WHERE id = %s;", (employee_id,))
    conn.commit()
    cur.close()
    conn.close()

def get_employee_by_code(code):
    """Находит сотрудника по его уникальному коду."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, code FROM employees WHERE code = %s;", (code,))
    employee = cur.fetchone()
    cur.close()
    conn.close()
    return employee

def check_if_ticket_granted_today(employee_id):
    """Проверяет, был ли уже выдан талон сотруднику сегодня."""
    conn = get_db_connection()
    cur = conn.cursor()
    today = date.today()
    cur.execute(
        "SELECT id FROM tickets WHERE employee_id = %s AND issue_date = %s;",
        (employee_id, today)
    )
    ticket = cur.fetchone()
    cur.close()
    conn.close()
    return ticket is not None

def grant_ticket(employee_id):
    """Записывает в БД информацию о выдаче талона."""
    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.now()
    cur.execute(
        "INSERT INTO tickets (employee_id, issue_date, issue_time) VALUES (%s, %s, %s);",
        (employee_id, now.date(), now.time())
    )
    conn.commit()
    cur.close()
    conn.close()

def get_daily_report():
    """Получает данные для ежедневного отчета."""
    conn = get_db_connection()
    cur = conn.cursor()
    today = date.today()
    cur.execute("""
        SELECT e.name, t.issue_time
        FROM tickets t
        JOIN employees e ON t.employee_id = e.id
        WHERE t.issue_date = %s
        ORDER BY t.issue_time;
    """, (today,))
    report_data = cur.fetchall()
    cur.close()
    conn.close()
    return report_data

def get_monthly_report(month, year):
    """Получает данные для ежемесячного отчета."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.name, t.issue_date, t.issue_time
        FROM tickets t
        JOIN employees e ON t.employee_id = e.id
        WHERE EXTRACT(MONTH FROM t.issue_date) = %s AND EXTRACT(YEAR FROM t.issue_date) = %s
        ORDER BY t.issue_date, t.issue_time;
    """, (month, year))
    report_data = cur.fetchall()
    cur.close()
    conn.close()
    return report_data
