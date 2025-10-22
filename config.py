import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "your-secret-key")
    DATABASE_URL = os.environ.get("DATABASE_URL")