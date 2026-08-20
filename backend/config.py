import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
    DATABASE_PORT = int(os.getenv("DATABASE_PORT", 3306))
    DATABASE_USER = os.getenv("DATABASE_USER", "root")
    DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "speed_detection")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    VIOLATIONS_FOLDER = os.path.join(BASE_DIR, "violations")
    MODEL_PATH = os.path.join(BASE_DIR, "..", "models", "yolo11n.pt")
    VIDEO_PATH = os.path.join(BASE_DIR, "..", "videos", "trash.mp4")
    FRONTEND_FOLDER = os.path.join(BASE_DIR, "..", "frontend")
    PROJECT_ROOT = os.path.join(BASE_DIR, "..")
    CONFIDENCE = 0.3
    VEHICLE_CLASSES = [2, 3, 5, 7]
    MODEL_SHA256 = "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"

    JWT_EXPIRY_HOURS = 8
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15
    MIN_PASSWORD_LENGTH = 8
    RATE_LIMIT_LOGIN = "10/minute"
    RATE_LIMIT_API = "120/minute"
    RATE_LIMIT_DETECT = "5/minute"
