import unittest
from unittest.mock import patch, MagicMock
import logging
from db import get_db_connection
from config import Config

# Настройка логирования для тестов
logger = logging.getLogger('db')
logger.setLevel(logging.INFO)

class LogCaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_capture = []

    def emit(self, record):
        self.log_capture.append(f"{record.levelname}: {record.getMessage()}")

class TestDatabaseConnection(unittest.TestCase):
    def setUp(self):
        # Настройка захвата логов
        self.log_capture_handler = LogCaptureHandler()
        self.log_capture_handler.setLevel(logging.INFO)
        logger.handlers = []  # Очищаем существующие обработчики
        logger.addHandler(self.log_capture_handler)

    def tearDown(self):
        # Очистка обработчиков
        logger.handlers = []

    @patch('db.psycopg2.connect')
    def test_get_db_connection_success(self, mock_connect):
        """Проверка успешного подключения к базе данных"""
        # Мок успешного соединения
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        # Вызов функции
        conn, status = get_db_connection()

        # Проверки
        self.assertEqual(conn, mock_conn)
        self.assertEqual(status, {"status": "success", "message": "Подключение к базе данных успешно"})
        mock_connect.assert_called_once_with(Config.DATABASE_URL)
        self.assertIn("INFO: Подключение к базе успешно!", self.log_capture_handler.log_capture)

    @patch('db.psycopg2.connect')
    def test_get_db_connection_failure(self, mock_connect):
        """Проверка ошибки подключения к базе данных"""
        # Мок ошибки соединения
        error_message = "Connection refused"
        mock_connect.side_effect = Exception(error_message)

        # Вызов функции
        conn, status = get_db_connection()

        # Проверки
        self.assertIsNone(conn)
        self.assertEqual(status["status"], "error")
        self.assertEqual(status["message"], f"Ошибка подключения к базе: {error_message}")
        mock_connect.assert_called_once_with(Config.DATABASE_URL)
        self.assertIn(f"ERROR: Ошибка подключения к базе: {error_message}", self.log_capture_handler.log_capture)

if __name__ == '__main__':
    unittest.main()