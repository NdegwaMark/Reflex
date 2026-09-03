"""Delivery API Routes"""
from flask import Blueprint, request, jsonify, current_app
from models import db, Delivery, DeliveryStatusLog, User, Notification
from auth import token_required, role_required
from datetime import datetime
import qrcode
import os
import uuid

deliveries_bp = Blueprint('deliveries', __name__)

@deliveries_bp.route('/deliveries', methods=['GET'])
@token_required
def get_deliveries(current_user):
    """Get deliveries based on user role with filtering"""
    status = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = Delivery.query

    # Role-based filtering
    if current_user.role == 'retailer':
        query = query.filter_by(retailer_id=current_user.id)
    elif current_user.role == 'rider':
        query = query.filter_by(rider_id=current_user.id)
    elif current_user.role == 'dispatcher':
        # Dispatchers see unassigned + their assigned
        query = query.filter(
            (Delivery.dispatcher_id == current_user.id) | 
            (Delivery.status == Delivery.STATUS_PENDING)
        )

    if status:
        query = query.filter_by(status=status)

    # Sort by newest first
    query = query.order_by(Delivery.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'deliveries': [d.to_dict(include_history=False) for d in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'per_page': per_page
    })

@deliveries_bp.route('/deliveries/<public_id>', methods=['GET'])
@token_required
def get_delivery(current_user, public_id):
    """Get single delivery details"""
    delivery = Delivery.query.filter_by(public_id=public_id).first_or_404()

    # Authorization check
    if current_user.role == 'retailer' and delivery.retailer_id != current_user.id:
        return jsonify({'message': 'Not authorized'}), 403
    if current_user.role == 'rider' and delivery.rider_id != current_user.id:
        return jsonify({'message': 'Not authorized'}), 403

    return jsonify({'delivery': delivery.to_dict(include_history=True)})

@deliveries_bp.route('/deliveries', methods=['POST'])
@token_required
@role_required(['retailer', 'admin'])
def create_delivery(current_user):
    """Create a new delivery request (Retailer)"""
    data = request.get_json()

    required = ['customer_name', 'customer_phone', 'customer_address', 'item_description']
    for field in required:
        if not data.get(field):
            return jsonify({'message': f'{field} is required'}), 400

    # Generate unique QR code
    qr_value = f"REFLEX-{uuid.uuid4().hex[:12].upper()}"

    delivery = Delivery(
        retailer_id=current_user.id,
        customer_name=data['customer_name'],
        customer_phone=data['customer_phone'],
        customer_address=data['customer_address'],
        customer_lat=data.get('customer_lat'),
        customer_lng=data.get('customer_lng'),
        item_description=data['item_description'],
        item_value=data.get('item_value'),
        delivery_notes=data.get('delivery_notes'),
        status=Delivery.STATUS_PENDING,
        qr_code=qr_value,
        estimated_delivery=data.get('estimated_delivery')
    )

    db.session.add(delivery)
    db.session.flush()  # Get ID without committing

    # Generate QR code image
    qr_dir = current_app.config['QR_CODE_DIR']
    qr_filename = f"{delivery.public_id}.png"
    qr_path = os.path.join(qr_dir, qr_filename)

    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_value)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_path)

    delivery.qr_code_path = f"/static/qr_codes/{qr_filename}"

    # Log creation
    log = DeliveryStatusLog(
        delivery_id=delivery.id,
        status=Delivery.STATUS_PENDING,
        updated_by=current_user.id,
        notes=f"Delivery request created by {current_user.name}"
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'message': 'Delivery request created successfully',
        'delivery': delivery.to_dict()
    }), 201

@deliveries_bp.route('/deliveries/<public_id>/status', methods=['PUT'])
@token_required
def update_status(current_user, public_id):
    """Update delivery status (Rider, Dispatcher, Admin)"""
    delivery = Delivery.query.filter_by(public_id=public_id).first_or_404()
    data = request.get_json()
    new_status = data.get('status')
    notes = data.get('notes', '')

    if not new_status or new_status not in Delivery.VALID_STATUSES:
        return jsonify({'message': 'Invalid status'}), 400

    # Authorization
    if current_user.role == 'rider' and delivery.rider_id != current_user.id:
        return jsonify({'message': 'Not assigned to you'}), 403
    if current_user.role == 'retailer' and delivery.retailer_id != current_user.id:
        return jsonify({'message': 'Not your delivery'}), 403

    # Validate status transitions
    valid_transitions = {
        Delivery.STATUS_PENDING: [Delivery.STATUS_ASSIGNED, Delivery.STATUS_CANCELLED],
        Delivery.STATUS_ASSIGNED: [Delivery.STATUS_PICKED_UP, Delivery.STATUS_FAILED, Delivery.STATUS_CANCELLED],
        Delivery.STATUS_PICKED_UP: [Delivery.STATUS_IN_TRANSIT, Delivery.STATUS_FAILED],
        Delivery.STATUS_IN_TRANSIT: [Delivery.STATUS_DELIVERED, Delivery.STATUS_FAILED],
        Delivery.STATUS_DELIVERED: [],
        Delivery.STATUS_FAILED: [Delivery.STATUS_ASSIGNED],
        Delivery.STATUS_CANCELLED: []
    }

    if new_status not in valid_transitions.get(delivery.status, []):
        return jsonify({
            'message': f'Cannot transition from {delivery.status} to {new_status}'
        }), 400

    old_status = delivery.status
    delivery.status = new_status
    delivery.status_updated_at = datetime.utcnow()

    if new_status == Delivery.STATUS_DELIVERED:
        delivery.actual_delivery = datetime.utcnow()

    # Log the change
    log = DeliveryStatusLog(
        delivery_id=delivery.id,
        status=new_status,
        updated_by=current_user.id,
        notes=notes,
        location_lat=data.get('location_lat'),
        location_lng=data.get('location_lng')
    )
    db.session.add(log)

    # Create notifications
    _create_status_notifications(delivery, old_status, new_status, current_user)

    db.session.commit()

    return jsonify({
        'message': 'Status updated',
        'delivery': delivery.to_dict()
    })

def _create_status_notifications(delivery, old_status, new_status, updated_by):
    """Create notifications for status changes"""
    notifications = []

    # Notify retailer on significant changes
    if new_status in [Delivery.STATUS_ASSIGNED, Delivery.STATUS_PICKED_UP, 
                      Delivery.STATUS_DELIVERED, Delivery.STATUS_FAILED]:
        msg = f"Delivery to {delivery.customer_name} is now {new_status.replace('_', ' ').title()}"
        if delivery.rider and new_status == Delivery.STATUS_ASSIGNED:
            msg += f" (Rider: {delivery.rider.name})"

        notifications.append(Notification(
            user_id=delivery.retailer_id,
            delivery_id=delivery.id,
            title="Delivery Update",
            message=msg,
            notification_type='status_update'
        ))

    # Notify rider on assignment
    if new_status == Delivery.STATUS_ASSIGNED and delivery.rider_id:
        notifications.append(Notification(
            user_id=delivery.rider_id,
            delivery_id=delivery.id,
            title="New Assignment",
            message=f"New delivery to {delivery.customer_address}",
            notification_type='assignment'
        ))

    for n in notifications:
        db.session.add(n)

@deliveries_bp.route('/deliveries/<public_id>/confirm', methods=['POST'])
@token_required
def confirm_delivery(current_user, public_id):
    """Confirm delivery via QR code or other method"""
    delivery = Delivery.query.filter_by(public_id=public_id).first_or_404()
    data = request.get_json()

    # Verify QR code
    qr_input = data.get('qr_code')
    if qr_input and qr_input != delivery.qr_code:
        return jsonify({'message': 'Invalid QR code'}), 400

    if delivery.status != Delivery.STATUS_IN_TRANSIT:
        return jsonify({'message': 'Delivery must be in transit to confirm'}), 400

    delivery.status = Delivery.STATUS_DELIVERED
    delivery.confirmed_at = datetime.utcnow()
    delivery.confirmed_by = data.get('confirmed_by', current_user.name)
    delivery.confirmation_method = data.get('method', 'qr_scan')
    delivery.actual_delivery = datetime.utcnow()

    if data.get('signature'):
        delivery.signature_data = data['signature']

    log = DeliveryStatusLog(
        delivery_id=delivery.id,
        status=Delivery.STATUS_DELIVERED,
        updated_by=current_user.id,
        notes=f"Confirmed via {delivery.confirmation_method}"
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'message': 'Delivery confirmed successfully',
        'delivery': delivery.to_dict()
    })

@deliveries_bp.route('/deliveries/<public_id>/qr', methods=['GET'])
@token_required
def get_qr_code(current_user, public_id):
    """Get QR code for a delivery"""
    delivery = Delivery.query.filter_by(public_id=public_id).first_or_404()

    if current_user.role == 'retailer' and delivery.retailer_id != current_user.id:
        return jsonify({'message': 'Not authorized'}), 403

    return jsonify({
        'qr_code': delivery.qr_code,
        'qr_image_url': delivery.qr_code_path,
        'customer_name': delivery.customer_name
    })
