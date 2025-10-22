import psycopg2
from config import Config
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    try:
        conn = psycopg2.connect(Config.DATABASE_URL)
        logger.info("Подключение к базе успешно!")
        return conn, {"status": "success", "message": "Подключение к базе данных успешно"}
    except Exception as e:
        logger.error(f"Ошибка подключения к базе: {str(e)}")
        return None, {"status": "error", "message": f"Ошибка подключения к базе: {str(e)}"}