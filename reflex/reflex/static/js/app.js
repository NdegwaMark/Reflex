// Reflex Core Utilities

function getToken() {
    return localStorage.getItem('reflex_token') || '';
}

function getUser() {
    try {
        return JSON.parse(localStorage.getItem('reflex_user') || '{}');
    } catch {
        return {};
    }
}

async function apiRequest(url, method = 'GET', body = null) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`
    };

    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    const res = await fetch(url, options);
    const data = await res.json();

    if (!res.ok) {
        const err = new Error(data.message || 'Request failed');
        err.status = res.status;
        throw err;
    }

    return data;
}

const apiGet = (url) => apiRequest(url, 'GET');
const apiPost = (url, body) => apiRequest(url, 'POST', body);
const apiPut = (url, body) => apiRequest(url, 'PUT', body);

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span> ${escapeHtml(message)}`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatStatus(status) {
    return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function getStatusColor(status) {
    const colors = {
        pending: '#f59e0b',
        assigned: '#3b82f6',
        picked_up: '#8b5cf6',
        in_transit: '#06b6d4',
        delivered: '#10b981',
        failed: '#ef4444',
        cancelled: '#6b7280'
    };
    return colors[status] || '#94a3b8';
}

function timeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'Just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-KE', {
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Logout handler
document.addEventListener('DOMContentLoaded', () => {
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await fetch('/api/auth/logout', { method: 'POST' });
            localStorage.removeItem('reflex_token');
            localStorage.removeItem('reflex_user');
            window.location.href = '/login';
        });
    }

    // Check auth
    const user = getUser();
    const path = window.location.pathname;
    if (path !== '/login' && !getToken()) {
        window.location.href = '/login';
    }
});
