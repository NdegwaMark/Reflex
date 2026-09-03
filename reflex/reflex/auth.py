"""Authentication & Authorization utilities"""
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from models import User

def generate_token(user):
    """Generate JWT token for user"""
    payload = {
        'public_id': user.public_id,
        'role': user.role,
        'name': user.name,
        'exp': datetime.utcnow() + current_app.config['JWT_EXPIRATION'],
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET'], algorithm='HS256')

def decode_token(token):
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, current_app.config['JWT_SECRET'], algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def token_required(f):
    """Decorator to protect routes with JWT"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Check header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Token malformed'}), 401

        # Check cookies for web views
        if not token and request.cookies.get('access_token'):
            token = request.cookies.get('access_token')

        if not token:
            return jsonify({'message': 'Authentication required'}), 401

        payload = decode_token(token)
        if not payload:
            return jsonify({'message': 'Token invalid or expired'}), 401

        current_user = User.query.filter_by(public_id=payload['public_id']).first()
        if not current_user or not current_user.is_active:
            return jsonify({'message': 'User not found or inactive'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

def role_required(allowed_roles):
    """Decorator to check user roles"""
    def decorator(f):
        @wraps(f)
        def decorated(current_user, *args, **kwargs):
            if current_user.role not in allowed_roles:
                return jsonify({'message': 'Insufficient permissions'}), 403
            return f(current_user, *args, **kwargs)
        return decorated
    return decorator
