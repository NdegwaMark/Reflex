"""Reflex Data Models"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # retailer, dispatcher, rider, admin
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Rider-specific fields
    vehicle_type = db.Column(db.String(50), nullable=True)  # motorcycle, bicycle, van
    vehicle_plate = db.Column(db.String(20), nullable=True)
    current_lat = db.Column(db.Float, nullable=True)
    current_lng = db.Column(db.Float, nullable=True)
    location_updated_at = db.Column(db.DateTime, nullable=True)
    is_available = db.Column(db.Boolean, default=True)

    # Relationships
    deliveries_as_rider = db.relationship('Delivery', foreign_keys='Delivery.rider_id', backref='rider', lazy=True)
    deliveries_as_dispatcher = db.relationship('Delivery', foreign_keys='Delivery.dispatcher_id', backref='dispatcher', lazy=True)
    status_logs = db.relationship('DeliveryStatusLog', backref='updated_by_user', lazy=True)

    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.public_id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'is_available': self.is_available,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }
        if self.role == 'rider':
            data['vehicle_type'] = self.vehicle_type
            data['vehicle_plate'] = self.vehicle_plate
            data['current_location'] = {
                'lat': self.current_lat,
                'lng': self.current_lng,
                'updated_at': self.location_updated_at.isoformat() if self.location_updated_at else None
            } if self.current_lat else None
        if include_sensitive:
            data['internal_id'] = self.id
        return data


class Delivery(db.Model):
    __tablename__ = 'deliveries'

    STATUS_PENDING = 'pending'
    STATUS_ASSIGNED = 'assigned'
    STATUS_PICKED_UP = 'picked_up'
    STATUS_IN_TRANSIT = 'in_transit'
    STATUS_DELIVERED = 'delivered'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'

    VALID_STATUSES = [
        STATUS_PENDING, STATUS_ASSIGNED, STATUS_PICKED_UP,
        STATUS_IN_TRANSIT, STATUS_DELIVERED, STATUS_FAILED, STATUS_CANCELLED
    ]

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True, default=lambda: str(uuid.uuid4()))

    # Retailer info
    retailer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    retailer = db.relationship('User', foreign_keys=[retailer_id], backref='logged_deliveries')

    # Customer info
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_address = db.Column(db.Text, nullable=False)
    customer_lat = db.Column(db.Float, nullable=True)
    customer_lng = db.Column(db.Float, nullable=True)

    # Delivery details
    item_description = db.Column(db.Text, nullable=False)
    item_value = db.Column(db.Float, nullable=True)
    delivery_notes = db.Column(db.Text, nullable=True)

    # Assignment
    rider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    dispatcher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_at = db.Column(db.DateTime, nullable=True)

    # Status & Tracking
    status = db.Column(db.String(20), default=STATUS_PENDING)
    status_updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # QR Code for confirmation
    qr_code = db.Column(db.String(100), unique=True, nullable=True)
    qr_code_path = db.Column(db.String(255), nullable=True)

    # Confirmation
    confirmed_at = db.Column(db.DateTime, nullable=True)
    confirmed_by = db.Column(db.String(100), nullable=True)  # Name of person who confirmed
    confirmation_method = db.Column(db.String(20), nullable=True)  # qr_scan, signature, photo
    delivery_photo = db.Column(db.String(255), nullable=True)
    signature_data = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    estimated_delivery = db.Column(db.DateTime, nullable=True)
    actual_delivery = db.Column(db.DateTime, nullable=True)

    # Relationships
    status_logs = db.relationship('DeliveryStatusLog', backref='delivery', lazy=True, 
                                   order_by='DeliveryStatusLog.created_at.desc()')

    def to_dict(self, include_history=False):
        data = {
            'id': self.public_id,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'customer_address': self.customer_address,
            'customer_location': {
                'lat': self.customer_lat,
                'lng': self.customer_lng
            } if self.customer_lat else None,
            'item_description': self.item_description,
            'item_value': self.item_value,
            'delivery_notes': self.delivery_notes,
            'status': self.status,
            'status_updated_at': self.status_updated_at.isoformat() if self.status_updated_at else None,
            'qr_code': self.qr_code,
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
            'confirmed_by': self.confirmed_by,
            'confirmation_method': self.confirmation_method,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'estimated_delivery': self.estimated_delivery.isoformat() if self.estimated_delivery else None,
            'actual_delivery': self.actual_delivery.isoformat() if self.actual_delivery else None,
            'retailer': self.retailer.to_dict() if self.retailer else None,
            'rider': self.rider.to_dict() if self.rider else None,
            'dispatcher': self.dispatcher.to_dict() if self.dispatcher else None,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
        }
        if include_history:
            data['status_history'] = [log.to_dict() for log in self.status_logs]
        return data


class DeliveryStatusLog(db.Model):
    __tablename__ = 'delivery_status_logs'

    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey('deliveries.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    location_lat = db.Column(db.Float, nullable=True)
    location_lng = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'status': self.status,
            'updated_by': self.updated_by_user.to_dict() if self.updated_by_user else None,
            'notes': self.notes,
            'location': {
                'lat': self.location_lat,
                'lng': self.location_lng
            } if self.location_lat else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref='notifications')
    delivery_id = db.Column(db.Integer, db.ForeignKey('deliveries.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), default='general')  # assignment, status_update, alert
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'type': self.notification_type,
            'is_read': self.is_read,
            'delivery_id': self.delivery.public_id if self.delivery else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
