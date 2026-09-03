// Reflex Real-Time Socket.IO Client

let socket = null;

function initSocket() {
    const token = getToken();
    if (!token) return;

    socket = io();

    socket.on('connect', () => {
        console.log('Socket connected');
        socket.emit('authenticate', { token });
    });

    socket.on('authenticated', (data) => {
        console.log('Socket authenticated as', data.role);

        if (typeof currentDeliveryId !== 'undefined' && currentDeliveryId) {
            socket.emit('join_delivery_room', { delivery_id: currentDeliveryId });
        }
    });

    socket.on('auth_error', (data) => {
        console.error('Socket auth error:', data.message);
    });

    socket.on('delivery_status_changed', (data) => {
        console.log('Status change:', data);
        if (typeof onDeliveryUpdate === 'function') {
            onDeliveryUpdate(data);
        }
    });

    socket.on('new_delivery_available', (data) => {
        console.log('New delivery:', data);
        if (typeof onNewDelivery === 'function') {
            onNewDelivery(data);
        }
    });

    socket.on('new_delivery_request', (data) => {
        if (typeof onNewAssignment === 'function') {
            onNewAssignment(data);
        }
    });

    socket.on('rider_location_update', (data) => {
        console.log('Rider location:', data);
    });

    socket.on('disconnect', () => {
        console.log('Socket disconnected');
    });
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    if (getToken()) {
        initSocket();
    }
});
