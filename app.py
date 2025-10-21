from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
import psycopg2
import os
import bcrypt
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your-secret-key")

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Модель пользователя
class User(UserMixin):
    def __init__(self, user_id, username, email, role):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role

# Декоратор для проверки роли
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash("Доступ запрещён", "error")
                return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Подключение к базе данных
def get_db_connection():
    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        print("Подключение к базе успешно!")
        return conn, {"status": "success", "message": "Подключение к базе данных успешно"}
    except Exception as e:
        print(f"Ошибка подключения: {str(e)}")
        return None, {"status": "error", "message": f"Ошибка подключения к базе: {str(e)}"}

# Загрузка пользователя
@login_manager.user_loader
def load_user(user_id):
    conn, db_status = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT UserID, Username, Email, Role FROM Users WHERE UserID = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return User(user[0], user[1], user[2], user[3])
    return None

@app.route('/')
def index():
    conn, db_status = get_db_connection()
    if conn:
        conn.close()
    return render_template('index.html', db_status=db_status)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        conn, db_status = get_db_connection()
        if not conn:
            flash(db_status["message"], "error")
            return render_template('login.html')
        cursor = conn.cursor()
        cursor.execute("SELECT UserID, Username, Email, Password, Role FROM Users WHERE Username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and bcrypt.checkpw(password, user[3].encode('utf-8')):
            login_user(User(user[0], user[1], user[2], user[4]))
            flash("Вход выполнен успешно!", "success")
            return redirect(url_for('index'))
        flash("Неверное имя пользователя или пароль", "error")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        role = request.form.get('role', 'partner')
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
        conn, db_status = get_db_connection()
        if not conn:
            flash(db_status["message"], "error")
            return render_template('register.html')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO Users (Username, Email, Password, Role) VALUES (%s, %s, %s, %s)",
                (username, email, hashed_password, role)
            )
            conn.commit()
            flash("Регистрация успешна! Войдите в систему.", "success")
            cursor.close()
            conn.close()
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            conn.rollback()
            flash("Имя пользователя или email уже заняты", "error")
            cursor.close()
            conn.close()
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Вы вышли из системы", "success")
    return redirect(url_for('index'))

@app.route('/partners')
@login_required
@role_required('analyst', 'manager')
def partners():
    try:
        conn, db_status = get_db_connection()
        if not conn:
            return render_template('error.html', error=db_status["message"])
        cursor = conn.cursor()
        cursor.execute("""
            SELECT PartnerID, Name, LegalAddress, INN, DirectorFullName, Phone, Email, Rating,
                   fn_GetPartnerDiscount(PartnerID) AS Discount
            FROM Partners
        """)
        partners = cursor.fetchall()
        print(f"Найдено партнёров: {len(partners)}")
        for partner in partners:
            print(partner)
        cursor.close()
        conn.close()
        return render_template('partners.html', partners=partners)
    except Exception as e:
        error_message = f"Ошибка: {str(e)}. Проверьте подключение к базе или наличие данных в таблице Partners."
        print(error_message)
        return render_template('error.html', error=error_message)

@app.route('/calc', methods=['GET', 'POST'])
@login_required
@role_required('analyst', 'manager')
def calc():
    if request.method == 'POST':
        product_id = int(request.form['product_id'])
        material_id = int(request.form['material_id'])
        quantity = int(request.form['quantity'])
        param1 = float(request.form['param1'])
        param2 = float(request.form['param2'])
        conn, db_status = get_db_connection()
        if not conn:
            flash(db_status["message"], "error")
            return render_template('calc.html')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT fn_CalcRequiredMaterial(%s, %s, %s, %s, %s)",
            (product_id, material_id, quantity, param1, param2)
        )
        result = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        flash(f"Требуется материалов: {result}", "success")
        return render_template('calc.html', result=result)
    return render_template('calc.html')

if __name__ == '__main__':
    app.run(debug=True)