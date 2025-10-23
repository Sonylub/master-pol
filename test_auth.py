import unittest
from unittest.mock import patch, MagicMock
from flask import Flask, render_template
from flask_login import login_user, LoginManager, UserMixin
import bcrypt
from auth import auth_bp
from db import get_db_connection
from models import User
from config import Config
from partners import partners_bp
from requests import requests_bp
from supplies import supplies_bp
from products import products_bp
from materials import materials_bp
from upload import upload_bp
from calc import calc_bp
from users import users_bp

# Класс пользователя для тестов
class User(UserMixin):
    def __init__(self, user_id, username, email, role, partner_id=None):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role
        self.partner_id = partner_id

# Настройка приложения
app = Flask(__name__)
app.config.from_object(Config)
app.config['TESTING'] = True
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User(user_id, 'testuser', 'test@example.com', 'analyst')

# Регистрация всех блюпринтов
app.register_blueprint(auth_bp)
app.register_blueprint(partners_bp)
app.register_blueprint(requests_bp)
app.register_blueprint(supplies_bp)
app.register_blueprint(products_bp)
app.register_blueprint(materials_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(calc_bp)
app.register_blueprint(users_bp)

@app.route('/')
def index():
    conn, db_status = get_db_connection()
    partners = []
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT PartnerID, Name FROM Partners")
            partners = cursor.fetchall()
        except Exception as e:
            db_status = {'status': 'error', 'message': str(e)}
        finally:
            cursor.close()
            conn.close()
    return render_template('index.html', db_status=db_status, partners=partners)

class TestAuth(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.conn_mock = MagicMock()
        self.cursor_mock = MagicMock()
        self.conn_mock.cursor.return_value = self.cursor_mock
        self.db_status = {'status': 'success', 'message': 'OK'}

    def tearDown(self):
        self.app_context.pop()

    @patch('auth.get_db_connection')
    def test_login_success(self, mock_get_db_connection):
        """PT-01: Проверка успешного входа пользователя"""
        mock_get_db_connection.return_value = (self.conn_mock, self.db_status)
        hashed_password = bcrypt.hashpw('password'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        self.cursor_mock.fetchone.return_value = (1, 'testuser', 'test@example.com', hashed_password, 'analyst', None)

        with self.client:
            self.client.get('/')  # Инициализация сессии
            response = self.client.post('/login', data={
                'username': 'testuser',
                'password': 'password'
            }, follow_redirects=True)

        response_text = response.data.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Вход выполнен успешно!', response_text)
        self.assertIn('alert-success', response_text)
        self.assertIn('Мастер Пол', response_text)
        self.assertIn('Привет, testuser (analyst)!', response_text)  # Проверяем, что пользователь аутентифицирован
        self.cursor_mock.execute.assert_called_with(
            "SELECT UserID, Username, Email, Password, Role, PartnerID FROM Users WHERE Username = %s",
            ('testuser',)
        )

    @patch('auth.get_db_connection')
    def test_login_invalid_password(self, mock_get_db_connection):
        """NT-01: Проверка ошибки при неверном пароле"""
        mock_get_db_connection.return_value = (self.conn_mock, self.db_status)
        hashed_password = bcrypt.hashpw('correct_password'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        self.cursor_mock.fetchone.return_value = (1, 'testuser', 'test@example.com', hashed_password, 'analyst', None)

        with self.client:
            self.client.get('/')  # Инициализация сессии
            response = self.client.post('/login', data={
                'username': 'testuser',
                'password': 'wrong_password'
            }, follow_redirects=True)

        response_text = response.data.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Неверное имя пользователя или пароль', response_text)
        self.assertIn('alert-danger', response_text)
        self.assertIn('Вход', response_text)  # Остаёмся на странице логина

    @patch('auth.get_db_connection')
    def test_login_already_authenticated(self, mock_get_db_connection):
        """PT-02: Проверка редиректа для аутентифицированного пользователя"""
        mock_get_db_connection.return_value = (self.conn_mock, self.db_status)
        self.cursor_mock.fetchall.return_value = []

        with self.client:
            self.client.get('/')  # Инициализация сессии
            login_user(User(1, 'testuser', 'test@example.com', 'analyst'))
            response = self.client.get('/login', follow_redirects=True)

        response_text = response.data.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Вход', response_text)  # Не страница логина
        self.assertIn('Мастер Пол', response_text)
        self.assertIn('Привет, testuser (analyst)!', response_text)

    @patch('auth.get_db_connection')
    def test_login_nonexistent_user(self, mock_get_db_connection):
        """NT-02: Проверка ошибки при несуществующем имени пользователя"""
        mock_get_db_connection.return_value = (self.conn_mock, self.db_status)
        self.cursor_mock.fetchone.return_value = None

        with self.client:
            self.client.get('/')  # Инициализация сессии
            response = self.client.post('/login', data={
                'username': 'nonexistent',
                'password': 'password'
            }, follow_redirects=True)

        response_text = response.data.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Неверное имя пользователя или пароль', response_text)
        self.assertIn('alert-danger', response_text)
        self.assertIn('Вход', response_text)  # Остаёмся на странице логина

    @patch('auth.get_db_connection')
    def test_logout_success(self, mock_get_db_connection):
        """PT-03: Проверка успешного выхода пользователя"""
        mock_get_db_connection.return_value = (self.conn_mock, self.db_status)
        self.cursor_mock.fetchall.return_value = []

        with self.client:
            self.client.get('/')  # Инициализация сессии
            login_user(User(1, 'testuser', 'test@example.com', 'analyst'))
            response = self.client.get('/logout', follow_redirects=True)

        response_text = response.data.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Вы вышли из системы', response_text)
        self.assertIn('alert-success', response_text)
        self.assertIn('Мастер Пол', response_text)
        self.assertIn('Вход', response_text)  # После выхода видна ссылка на логин

    @patch('auth.get_db_connection')
    def test_logout_unauthenticated(self, mock_get_db_connection):
        """NT-03: Проверка выхода неаутентифицированного пользователя"""
        mock_get_db_connection.return_value = (self.conn_mock, self.db_status)
        self.cursor_mock.fetchall.return_value = []

        with self.client:
            self.client.get('/')  # Инициализация сессии
            response = self.client.get('/logout', follow_redirects=True)

        response_text = response.data.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Вы вышли из системы', response_text)
        self.assertIn('alert-success', response_text)
        self.assertIn('Мастер Пол', response_text)
        self.assertIn('Вход', response_text)  # Видна ссылка на логин

if __name__ == '__main__':
    unittest.main()