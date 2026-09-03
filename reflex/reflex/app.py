"""
Reflex - Delivery Coordination System for Kenyan Retailers
Main Application Entry Point
"""
import os
import sys
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, render_template, redirect, url_for, make_response
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from models import db, User, Delivery, DeliveryStatusLog, Notification
from auth import generate_token, token_required, role_required, decode_token
from api.deliveries import deliveries_bp
from api.dispatch import dispatch_bp
from api.riders import riders_bp

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
CORS(app)
socketio = SocketIO(app, async_mode=Config.SOCKETIO_ASYNC_MODE, 
                    cors_allowed_origins=Config.SOCKETIO_CORS_ALLOWED_ORIGINS)

# Register blueprints
app.register_blueprint(deliveries_bp, url_prefix='/api')
app.register_blueprint(dispatch_bp, url_prefix='/api')
app.register_blueprint(riders_bp, url_prefix='/api')

# ==================== AUTH ROUTES ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user (Admin only in production, open for demo)"""
    data = request.get_json()

    required = ['name', 'phone', 'password', 'role']
    for field in required:
        if not data.get(field):
            return jsonify({'message': f'{field} is required'}), 400

    if data['role'] not in ['retailer', 'dispatcher', 'rider', 'admin']:
        return jsonify({'message': 'Invalid role'}), 400

    if User.query.filter_by(phone=data['phone']).first():
        return jsonify({'message': 'Phone number already registered'}), 409

    user = User(
        name=data['name'],
        phone=data['phone'],
        email=data.get('email'),
        password_hash=generate_password_hash(data['password']),
        role=data['role'],
        vehicle_type=data.get('vehicle_type'),
        vehicle_plate=data.get('vehicle_plate'),
        is_available=data['role'] == 'rider'
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict()
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Authenticate user and return token"""
    data = request.get_json()
    phone = data.get('phone')
    password = data.get('password')

    if not phone or not password:
        return jsonify({'message': 'Phone and password required'}), 400

    user = User.query.filter_by(phone=phone).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'message': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'message': 'Account deactivated'}), 403

    user.last_login = datetime.utcnow()
    db.session.commit()

    token = generate_token(user)

    response = make_response(jsonify({
        'message': 'Login successful',
        'token': token,
        'user': user.to_dict()
    }))

    # Set cookie for web sessions
    response.set_cookie('access_token', token, httponly=True, max_age=86400, samesite='Lax')

    return response

@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    """Get current user profile"""
    return jsonify({'user': current_user.to_dict()})

@app.route('/api/auth/logout', methods=['POST'])
@token_required
def logout(current_user):
    """Logout user"""
    response = make_response(jsonify({'message': 'Logged out'}))
    response.delete_cookie('access_token')
    return response

# ==================== NOTIFICATION ROUTES ====================

@app.route('/api/notifications', methods=['GET'])
@token_required
def get_notifications(current_user):
    """Get user notifications"""
    unread_only = request.args.get('unread', 'false').lower() == 'true'

    query = Notification.query.filter_by(user_id=current_user.id)
    if unread_only:
        query = query.filter_by(is_read=False)

    notifications = query.order_by(Notification.created_at.desc()).limit(50).all()

    return jsonify({
        'notifications': [n.to_dict() for n in notifications],
        'unread_count': Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    })

@app.route('/api/notifications/<int:notification_id>/read', methods=['PUT'])
@token_required
def mark_notification_read(current_user, notification_id):
    """Mark notification as read"""
    notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    notification.is_read = True
    db.session.commit()
    return jsonify({'message': 'Marked as read'})

# ==================== WEB ROUTES (PWA) ====================

@app.route('/')
def index():
    """Landing page / redirect to appropriate dashboard"""
    token = request.cookies.get('access_token')
    if token:
        payload = decode_token(token)
        if payload:
            role = payload.get('role')
            if role == 'retailer':
                return redirect(url_for('retailer_dashboard'))
            elif role == 'dispatcher':
                return redirect(url_for('dispatcher_dashboard'))
            elif role == 'rider':
                return redirect(url_for('rider_dashboard'))
    return render_template('login.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/retailer')
def retailer_dashboard():
    return render_template('retailer.html')

@app.route('/dispatcher')
def dispatcher_dashboard():
    return render_template('dispatcher.html')

@app.route('/rider')
def rider_dashboard():
    return render_template('rider.html')

# ==================== SOCKET.IO EVENTS (REAL-TIME) ====================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to Reflex real-time service'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")

@socketio.on('authenticate')
def handle_authenticate(data):
    """Authenticate socket connection with JWT"""
    token = data.get('token')
    if not token:
        emit('auth_error', {'message': 'No token provided'})
        return

    payload = decode_token(token)
    if not payload:
        emit('auth_error', {'message': 'Invalid token'})
        return

    user = User.query.filter_by(public_id=payload['public_id']).first()
    if not user:
        emit('auth_error', {'message': 'User not found'})
        return

    # Join role-based room
    join_room(f"user_{user.public_id}")
    join_room(f"role_{user.role}")

    # Rider joins rider room for assignments
    if user.role == 'rider':
        join_room(f"rider_{user.public_id}")

    emit('authenticated', {
        'user_id': user.public_id,
        'role': user.role,
        'name': user.name
    })

@socketio.on('join_delivery_room')
def join_delivery_room(data):
    """Join a specific delivery room for real-time updates"""
    delivery_id = data.get('delivery_id')
    if delivery_id:
        join_room(f"delivery_{delivery_id}")
        emit('joined_room', {'delivery_id': delivery_id})

@socketio.on('leave_delivery_room')
def leave_delivery_room(data):
    """Leave a delivery room"""
    delivery_id = data.get('delivery_id')
    if delivery_id:
        leave_room(f"delivery_{delivery_id}")
        emit('left_room', {'delivery_id': delivery_id})

@socketio.on('update_location')
def handle_location_update(data):
    """Handle rider location updates"""
    token = data.get('token')
    if not token:
        return

    payload = decode_token(token)
    if not payload:
        return

    user = User.query.filter_by(public_id=payload['public_id']).first()
    if not user or user.role != 'rider':
        return

    lat = data.get('lat')
    lng = data.get('lng')

    if lat and lng:
        user.current_lat = lat
        user.current_lng = lng
        user.location_updated_at = datetime.utcnow()
        db.session.commit()

        # Broadcast to dispatchers watching this rider
        socketio.emit('rider_location_update', {
            'rider_id': user.public_id,
            'rider_name': user.name,
            'lat': lat,
            'lng': lng,
            'timestamp': datetime.utcnow().isoformat()
        }, room=f"role_dispatcher")

@socketio.on('status_update')
def handle_status_update(data):
    """Handle real-time status updates from riders"""
    token = data.get('token')
    delivery_id = data.get('delivery_id')
    new_status = data.get('status')
    notes = data.get('notes', '')

    if not all([token, delivery_id, new_status]):
        emit('error', {'message': 'Missing required fields'})
        return

    payload = decode_token(token)
    if not payload:
        emit('error', {'message': 'Invalid token'})
        return

    user = User.query.filter_by(public_id=payload['public_id']).first()
    delivery = Delivery.query.filter_by(public_id=delivery_id).first()

    if not delivery or not user:
        emit('error', {'message': 'Delivery or user not found'})
        return

    # Authorization
    if user.role == 'rider' and delivery.rider_id != user.id:
        emit('error', {'message': 'Not assigned to this delivery'})
        return

    # Update status
    old_status = delivery.status
    delivery.status = new_status
    delivery.status_updated_at = datetime.utcnow()

    if new_status == Delivery.STATUS_DELIVERED:
        delivery.actual_delivery = datetime.utcnow()

    log = DeliveryStatusLog(
        delivery_id=delivery.id,
        status=new_status,
        updated_by=user.id,
        notes=notes
    )
    db.session.add(log)
    db.session.commit()

    # Broadcast to all interested parties
    update_data = {
        'delivery_id': delivery_id,
        'old_status': old_status,
        'new_status': new_status,
        'updated_by': user.name,
        'updated_at': datetime.utcnow().isoformat(),
        'notes': notes
    }

    # Notify delivery room watchers
    socketio.emit('delivery_status_changed', update_data, room=f"delivery_{delivery_id}")

    # Notify retailer
    socketio.emit('delivery_status_changed', update_data, room=f"user_{delivery.retailer.public_id}")

    # Notify dispatcher
    if delivery.dispatcher_id:
        socketio.emit('delivery_status_changed', update_data, room=f"user_{delivery.dispatcher.public_id}")

    emit('status_update_confirmed', {'delivery': delivery.to_dict()})

@socketio.on('new_delivery_request')
def handle_new_delivery(data):
    """Broadcast new delivery to dispatchers"""
    token = data.get('token')
    if not token:
        return

    payload = decode_token(token)
    if not payload:
        return

    user = User.query.filter_by(public_id=payload['public_id']).first()
    if not user or user.role != 'retailer':
        return

    # Broadcast to all dispatchers
    socketio.emit('new_delivery_available', {
        'retailer_name': user.name,
        'timestamp': datetime.utcnow().isoformat()
    }, room="role_dispatcher")

# ==================== UTILITY ROUTES ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'Reflex',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/stats/overview', methods=['GET'])
@token_required
@role_required(['admin'])
def get_overview_stats(current_user):
    """Get system-wide statistics"""
    today = datetime.utcnow().date()

    stats = {
        'total_deliveries': Delivery.query.count(),
        'pending': Delivery.query.filter_by(status=Delivery.STATUS_PENDING).count(),
        'in_progress': Delivery.query.filter(
            Delivery.status.in_([Delivery.STATUS_ASSIGNED, Delivery.STATUS_PICKED_UP, Delivery.STATUS_IN_TRANSIT])
        ).count(),
        'delivered_today': Delivery.query.filter(
            Delivery.status == Delivery.STATUS_DELIVERED,
            db.func.date(Delivery.actual_delivery) == today
        ).count(),
        'total_users': User.query.count(),
        'active_riders': User.query.filter_by(role='rider', is_available=True).count(),
        'retailers': User.query.filter_by(role='retailer').count()
    }

    return jsonify({'stats': stats})

# ==================== DATABASE SETUP ====================

def create_default_data():
    """Create demo data for testing"""
    with app.app_context():
        db.create_all()

        # Check if admin exists
        if not User.query.filter_by(phone='254700000000').first():
            # Create demo users
            users = [
                User(name='Admin User', phone='254700000000', 
                     password_hash=generate_password_hash('admin123'), role='admin'),
                User(name='QuickMart Staff', phone='254711111111',
                     password_hash=generate_password_hash('retailer123'), role='retailer'),
                User(name='Naivas Staff', phone='254722222222',
                     password_hash=generate_password_hash('retailer123'), role='retailer'),
                User(name='John Dispatcher', phone='254733333333',
                     password_hash=generate_password_hash('dispatch123'), role='dispatcher'),
                User(name='Peter Rider', phone='254744444444',
                     password_hash=generate_password_hash('rider123'), role='rider',
                     vehicle_type='motorcycle', vehicle_plate='KBM 123A', is_available=True),
                User(name='Mary Rider', phone='254755555555',
                     password_hash=generate_password_hash('rider123'), role='rider',
                     vehicle_type='bicycle', vehicle_plate='N/A', is_available=True),
            ]

            for user in users:
                db.session.add(user)

            db.session.commit()
            print("✓ Demo data created")
            print("  Admin: 254700000000 / admin123")
            print("  Retailer: 254711111111 / retailer123")
            print("  Dispatcher: 254733333333 / dispatch123")
            print("  Rider: 254744444444 / rider123")

# ==================== MAIN ====================

if __name__ == '__main__':
    create_default_data()
    print("\n🚀 Reflex starting on http://localhost:5000")
    print("   WebSocket real-time enabled")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
