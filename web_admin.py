import os
from flask import Flask, render_template, request, redirect, url_for, Response
from functools import wraps
from dotenv import load_dotenv

# Импортируем функции для работы с БД
import database as db

load_dotenv()

app = Flask(__name__)

# --- Аутентификация ---

def check_auth(username, password):
    """Проверяет данные для входа."""
    return username == os.getenv('ADMIN_USERNAME') and password == os.getenv('ADMIN_PASSWORD')

def authenticate():
    """Отправляет заголовок для базовой аутентификации."""
    return Response(
        'Не удалось выполнить аутентификацию.\n'
        'Необходимы корректные учетные данные.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def auth_required(f):
    """Декоратор для защиты маршрутов."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# --- Маршруты ---

@app.route('/')
@auth_required
def index():
    """Главная страница со списком сотрудников."""
    employees = db.get_all_employees()
    return render_template('admin.html', employees=employees)

@app.route('/add', methods=['POST'])
@auth_required
def add_employee_route():
    """Обрабатывает добавление нового сотрудника."""
    name = request.form.get('name')
    code = request.form.get('code')
    if name and code:
        try:
            db.add_employee(name, code)
        except Exception as e:
            # Можно добавить обработку ошибки, если код уже существует
            print(f"Ошибка добавления сотрудника: {e}")
    return redirect(url_for('index'))

@app.route('/delete/<int:employee_id>', methods=['POST'])
@auth_required
def delete_employee_route(employee_id):
    """Обрабатывает удаление сотрудника."""
    db.remove_employee(employee_id)
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Для локального запуска
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
