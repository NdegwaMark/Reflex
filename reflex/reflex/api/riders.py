"""Rider API Routes"""
from flask import Blueprint, request, jsonify
from models import db, Delivery, User
from auth import token_required, role_required
from datetime import datetime

riders_bp = Blueprint('riders', __name__)

@riders_bp.route('/rider/deliveries', methods=['GET'])
@token_required
@role_required(['rider', 'admin'])
def get_my_deliveries(current_user):
    """Get deliveries assigned to current rider"""
    status = request.args.get('status')

    query = Delivery.query.filter_by(rider_id=current_user.id)

    if status:
        query = query.filter_by(status=status)
    else:
        # Default: show active deliveries
        query = query.filter(Delivery.status.in_([
            Delivery.STATUS_ASSIGNED,
            Delivery.STATUS_PICKED_UP,
            Delivery.STATUS_IN_TRANSIT
        ]))

    deliveries = query.order_by(Delivery.assigned_at.asc()).all()

    return jsonify({
        'deliveries': [d.to_dict(include_history=True) for d in deliveries]
    })

@riders_bp.route('/rider/deliveries/<public_id>/pickup', methods=['POST'])
@token_required
@role_required(['rider', 'admin'])
def mark_picked_up(current_user, public_id):
    """Mark delivery as picked up"""
    delivery = Delivery.query.filter_by(public_id=public_id, rider_id=current_user.id).first_or_404()

    if delivery.status != Delivery.STATUS_ASSIGNED:
        return jsonify({'message': 'Delivery must be assigned first'}), 400

    delivery.status = Delivery.STATUS_PICKED_UP
    delivery.status_updated_at = datetime.utcnow()

    from models import DeliveryStatusLog
    log = DeliveryStatusLog(
        delivery_id=delivery.id,
        status=Delivery.STATUS_PICKED_UP,
        updated_by=current_user.id,
        notes="Item picked up from retailer"
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({'message': 'Marked as picked up', 'delivery': delivery.to_dict()})

@riders_bp.route('/rider/deliveries/<public_id>/transit', methods=['POST'])
@token_required
@role_required(['rider', 'admin'])
def mark_in_transit(current_user, public_id):
    """Mark delivery as in transit"""
    delivery = Delivery.query.filter_by(public_id=public_id, rider_id=current_user.id).first_or_404()

    if delivery.status != Delivery.STATUS_PICKED_UP:
        return jsonify({'message': 'Must pick up first'}), 400

    delivery.status = Delivery.STATUS_IN_TRANSIT
    delivery.status_updated_at = datetime.utcnow()

    from models import DeliveryStatusLog
    log = DeliveryStatusLog(
        delivery_id=delivery.id,
        status=Delivery.STATUS_IN_TRANSIT,
        updated_by=current_user.id,
        notes="Heading to customer location"
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({'message': 'Marked as in transit', 'delivery': delivery.to_dict()})

@riders_bp.route('/rider/location', methods=['POST'])
@token_required
@role_required(['rider', 'admin'])
def update_location(current_user):
    """Update rider's current location"""
    data = request.get_json()
    lat = data.get('lat')
    lng = data.get('lng')

    if lat is None or lng is None:
        return jsonify({'message': 'lat and lng required'}), 400

    current_user.current_lat = lat
    current_user.current_lng = lng
    current_user.location_updated_at = datetime.utcnow()

    db.session.commit()

    return jsonify({'message': 'Location updated'})

@riders_bp.route('/rider/availability', methods=['PUT'])
@token_required
@role_required(['rider', 'admin'])
def update_availability(current_user):
    """Toggle rider availability"""
    data = request.get_json()
    available = data.get('available')

    if available is None:
        return jsonify({'message': 'available field required'}), 400

    current_user.is_available = available
    db.session.commit()

    return jsonify({
        'message': f"Availability set to {available}",
        'is_available': current_user.is_available
    })

@riders_bp.route('/rider/stats', methods=['GET'])
@token_required
@role_required(['rider', 'admin'])
def get_rider_stats(current_user):
    """Get rider performance stats"""
    today = datetime.utcnow().date()

    stats = {
        'total_delivered': Delivery.query.filter_by(
            rider_id=current_user.id,
            status=Delivery.STATUS_DELIVERED
        ).count(),
        'delivered_today': Delivery.query.filter(
            Delivery.rider_id == current_user.id,
            Delivery.status == Delivery.STATUS_DELIVERED,
            db.func.date(Delivery.actual_delivery) == today
        ).count(),
        'active_deliveries': Delivery.query.filter(
            Delivery.rider_id == current_user.id,
            Delivery.status.in_([Delivery.STATUS_ASSIGNED, Delivery.STATUS_PICKED_UP, Delivery.STATUS_IN_TRANSIT])
        ).count(),
        'failed_deliveries': Delivery.query.filter_by(
            rider_id=current_user.id,
            status=Delivery.STATUS_FAILED
        ).count()
    }

    return jsonify({'stats': stats})
