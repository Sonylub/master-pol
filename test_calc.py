import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_login import login_user, LoginManager, UserMixin
from calc import calc_bp
from db import get_db_connection

# Класс пользователя для тестов
class User(UserMixin):
    def __init__(self, username, role):
        self.id = username
        self.username = username
        self.role = role

# Настройка приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = 'test_secret_key'
app.config['TESTING'] = True
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User(user_id, 'analyst')  # По умолчанию аналитик

app.register_blueprint(calc_bp)

class TestCalc(unittest.TestCase):
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

    @patch('calc.get_db_connection')
    def test_calc_success_analyst(self, mock_get_db_connection):
        """PT-01: Проверка расчёта материалов для аналитика"""
        mock_get_db_connection.return_value = (self.conn_mock, self.db_status)
        self.cursor_mock.fetchall.side_effect = [
            [(1, 'Паркетная доска')],  # Products
            [(1, 'Древесина')],        # Materials
            [(1, 'Паркетная доска', 1, 'Древесина', 2.00)]  # ProductComposition
        ]
        self.cursor_mock.fetchone.return_value = [20.4]  # Результат fn_CalcRequiredMaterial

        with self.client:
            self.client.get('/')  # Инициализация сессии
            login_user(User('analyst1', 'analyst'))
            response = self.client.post('/calc', data={
                'product_id': 1,
                'material_id': 1,
                'quantity': 10,
                'param1': 0.1,
                'param2': 0.2
            }, follow_redirects=True)

        response_text = response.data.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Требуется материалов: 20.4', response_text)  # Исправлено: 20.4 вместо 20.40
        self.assertIn('alert-success', response_text)
        self.assertIn('OK', response_text)  # Проверка db_status
        self.cursor_mock.execute.assert_called_with(
            "SELECT fn_CalcRequiredMaterial(%s, %s, %s, %s, %s)",
            (1, 1, 10, 0.1, 0.2)
        )

    @patch('calc.get_db_connection')
    def test_calc_invalid_input(self, mock_get_db_connection):
        """NT-01: Проверка ошибки при неверных параметрах"""
        mock_get_db_connection.return_value = (self.conn_mock, self.db_status)
        self.cursor_mock.fetchall.return_value = [(1, 'Паркетная доска'), (1, 'Древесина')]
        self.cursor_mock.execute.side_effect = Exception('Связь не найдена')

        with self.client:
            self.client.get('/')  # Инициализация сессии
            login_user(User('analyst1', 'analyst'))
            response = self.client.post('/calc', data={
                'product_id': 1,
                'material_id': 999,
                'quantity': -10,
                'param1': -0.1,
                'param2': 0.2
            }, follow_redirects=True)

        response_text = response.data.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Ошибка: Связь не найдена', response_text)  # Исправлено: "Ошибка" вместо "Ошибка расчёта"
        self.assertIn('alert-danger', response_text)

    @patch('calc.get_db_connection')
    def test_calc_access_partner(self, mock_get_db_connection):
        """PT-02: Проверка доступа партнёра к /calc (без формы расчёта)"""
        mock_get_db_connection.return_value = (self.conn_mock, self.db_status)
        self.cursor_mock.fetchall.side_effect = [
            [(1, 'Паркетная доска')],  # Products
            [(1, 'Древесина')],        # Materials
            [(1, 'Паркетная доска', 1, 'Древесина', 2.00)]  # ProductComposition
        ]

        with self.client:
            self.client.get('/')  # Инициализация сессии
            login_user(User('aboba123', 'partner'))
            response = self.client.get('/calc')

        response_text = response.data.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Связи продукт-материал', response_text)
        self.assertNotIn('Рассчитать потребность в материалах', response_text)  # Форма недоступна

if __name__ == '__main__':
    unittest.main()