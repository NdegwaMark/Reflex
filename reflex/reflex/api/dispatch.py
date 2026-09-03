"""Dispatcher API Routes"""
from flask import Blueprint, request, jsonify
from models import db, Delivery, User, Notification
from auth import token_required, role_required
from datetime import datetime

dispatch_bp = Blueprint('dispatch', __name__)

@dispatch_bp.route('/dispatch/open-requests', methods=['GET'])
@token_required
@role_required(['dispatcher', 'admin'])
def get_open_requests(current_user):
    """Get all pending delivery requests"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    query = Delivery.query.filter_by(status=Delivery.STATUS_PENDING)\
        .order_by(Delivery.created_at.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'deliveries': [d.to_dict() for d in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })

@dispatch_bp.route('/dispatch/assign', methods=['POST'])
@token_required
@role_required(['dispatcher', 'admin'])
def assign_delivery(current_user):
    """Assign a delivery to a rider"""
    data = request.get_json()
    delivery_id = data.get('delivery_id')
    rider_id = data.get('rider_id')

    if not delivery_id or not rider_id:
        return jsonify({'message': 'delivery_id and rider_id required'}), 400

    delivery = Delivery.query.filter_by(public_id=delivery_id).first_or_404()
    rider = User.query.filter_by(public_id=rider_id).first_or_404()

    if rider.role != 'rider':
        return jsonify({'message': 'Selected user is not a rider'}), 400

    if not rider.is_available:
        return jsonify({'message': 'Rider is not available'}), 400

    if delivery.status != Delivery.STATUS_PENDING:
        return jsonify({'message': f'Delivery is already {delivery.status}'}), 400

    delivery.rider_id = rider.id
    delivery.dispatcher_id = current_user.id
    delivery.status = Delivery.STATUS_ASSIGNED
    delivery.assigned_at = datetime.utcnow()
    delivery.status_updated_at = datetime.utcnow()

    # Log assignment
    from models import DeliveryStatusLog
    log = DeliveryStatusLog(
        delivery_id=delivery.id,
        status=Delivery.STATUS_ASSIGNED,
        updated_by=current_user.id,
        notes=f"Assigned to rider {rider.name} by dispatcher {current_user.name}"
    )
    db.session.add(log)

    # Notify rider
    notification = Notification(
        user_id=rider.id,
        delivery_id=delivery.id,
        title="New Delivery Assignment",
        message=f"Deliver to: {delivery.customer_address}. Item: {delivery.item_description[:50]}...",
        notification_type='assignment'
    )
    db.session.add(notification)

    # Notify retailer
    retailer_notification = Notification(
        user_id=delivery.retailer_id,
        delivery_id=delivery.id,
        title="Delivery Assigned",
        message=f"Your delivery to {delivery.customer_name} has been assigned to {rider.name}",
        notification_type='assignment'
    )
    db.session.add(retailer_notification)

    db.session.commit()

    return jsonify({
        'message': 'Delivery assigned successfully',
        'delivery': delivery.to_dict()
    })

@dispatch_bp.route('/dispatch/batch-assign', methods=['POST'])
@token_required
@role_required(['dispatcher', 'admin'])
def batch_assign(current_user):
    """Batch assign multiple deliveries to a rider"""
    data = request.get_json()
    delivery_ids = data.get('delivery_ids', [])
    rider_id = data.get('rider_id')

    if not delivery_ids or not rider_id:
        return jsonify({'message': 'delivery_ids and rider_id required'}), 400

    rider = User.query.filter_by(public_id=rider_id).first_or_404()
    if rider.role != 'rider':
        return jsonify({'message': 'Not a rider'}), 400

    results = []
    for did in delivery_ids:
        delivery = Delivery.query.filter_by(public_id=did).first()
        if delivery and delivery.status == Delivery.STATUS_PENDING:
            delivery.rider_id = rider.id
            delivery.dispatcher_id = current_user.id
            delivery.status = Delivery.STATUS_ASSIGNED
            delivery.assigned_at = datetime.utcnow()

            from models import DeliveryStatusLog
            log = DeliveryStatusLog(
                delivery_id=delivery.id,
                status=Delivery.STATUS_ASSIGNED,
                updated_by=current_user.id,
                notes=f"Batch assigned to {rider.name}"
            )
            db.session.add(log)
            results.append(delivery.public_id)

    db.session.commit()

    return jsonify({
        'message': f'Assigned {len(results)} deliveries',
        'assigned': results
    })

@dispatch_bp.route('/dispatch/riders/available', methods=['GET'])
@token_required
@role_required(['dispatcher', 'admin'])
def get_available_riders(current_user):
    """Get list of available riders with current load"""
    riders = User.query.filter_by(role='rider', is_active=True, is_available=True).all()

    result = []
    for rider in riders:
        # Count active deliveries
        active_count = Delivery.query.filter(
            Delivery.rider_id == rider.id,
            Delivery.status.in_([Delivery.STATUS_ASSIGNED, Delivery.STATUS_PICKED_UP, Delivery.STATUS_IN_TRANSIT])
        ).count()

        rider_data = rider.to_dict()
        rider_data['active_deliveries'] = active_count
        result.append(rider_data)

    # Sort by least active deliveries
    result.sort(key=lambda x: x['active_deliveries'])

    return jsonify({'riders': result})

@dispatch_bp.route('/dispatch/dashboard', methods=['GET'])
@token_required
@role_required(['dispatcher', 'admin'])
def dispatcher_dashboard(current_user):
    """Get dispatcher dashboard stats"""
    stats = {
        'pending': Delivery.query.filter_by(status=Delivery.STATUS_PENDING).count(),
        'assigned': Delivery.query.filter_by(status=Delivery.STATUS_ASSIGNED).count(),
        'in_transit': Delivery.query.filter_by(status=Delivery.STATUS_IN_TRANSIT).count(),
        'delivered_today': Delivery.query.filter(
            Delivery.status == Delivery.STATUS_DELIVERED,
            db.func.date(Delivery.actual_delivery) == db.func.date(datetime.utcnow())
        ).count(),
        'available_riders': User.query.filter_by(role='rider', is_available=True).count(),
        'failed_today': Delivery.query.filter(
            Delivery.status == Delivery.STATUS_FAILED,
            db.func.date(Delivery.status_updated_at) == db.func.date(datetime.utcnow())
        ).count()
    }

    return jsonify({'stats': stats})
