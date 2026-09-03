"""Reflex Configuration"""
import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'reflex-dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///reflex.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET = os.environ.get('JWT_SECRET', 'reflex-jwt-secret-change-me')
    JWT_EXPIRATION = timedelta(hours=24)

    # SocketIO config
    SOCKETIO_ASYNC_MODE = 'eventlet'
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"

    # App settings
    APP_NAME = "Reflex"
    COMPANY_NAME = os.environ.get('COMPANY_NAME', 'Your Retail Business')

    # QR Code settings
    QR_CODE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'qr_codes')
    os.makedirs(QR_CODE_DIR, exist_ok=True)
