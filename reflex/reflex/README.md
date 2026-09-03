# ⚡ Reflex

Delivery Coordination System for Small Kenyan Retailers

## Overview

Reflex solves the chaos of coordinating deliveries for small retailers. It provides a simple, mobile-first platform where:

- **Retailers** log delivery requests with customer details
- **Dispatchers** assign deliveries to available riders
- **Riders** update status in real-time and confirm deliveries via QR code

## Features

- ✅ Real-time status updates via WebSockets
- ✅ QR code generation and scanning for delivery confirmation
- ✅ Role-based dashboards (Retailer, Dispatcher, Rider)
- ✅ Progressive Web App (works on any smartphone)
- ✅ Location tracking for riders
- ✅ Delivery history and audit trail
- ✅ Docker deployment ready

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask + Flask-SocketIO |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Real-time | WebSockets (SocketIO) |
| Auth | JWT |
| Frontend | Vanilla HTML/JS PWA |
| QR Codes | qrcode + html5-qrcode |
| Deployment | Docker + Gunicorn + Nginx |

## Quick Start

### Local Development

```bash
# 1. Clone the repository
git clone https://github.com/NdegwaMark/Reflex.git
cd Reflex

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python app.py

# 5. Open browser
# http://localhost:5000
```

### Docker Deployment

```bash
# Build and run
docker-compose up --build -d

# Access at http://localhost:5000
```

## Demo Accounts

| Role | Phone | Password |
|------|-------|----------|
| Admin | 254700000000 | admin123 |
| Retailer | 254711111111 | retailer123 |
| Dispatcher | 254733333333 | dispatch123 |
| Rider | 254744444444 | rider123 |

## API Documentation

### Authentication
- `POST /api/auth/login` - Login with phone and password
- `POST /api/auth/register` - Register new user
- `GET /api/auth/me` - Get current user

### Deliveries
- `GET /api/deliveries` - List deliveries (role-based)
- `POST /api/deliveries` - Create new delivery request
- `GET /api/deliveries/<id>` - Get delivery details
- `PUT /api/deliveries/<id>/status` - Update delivery status
- `POST /api/deliveries/<id>/confirm` - Confirm delivery

### Dispatch
- `GET /api/dispatch/open-requests` - View pending requests
- `POST /api/dispatch/assign` - Assign delivery to rider
- `GET /api/dispatch/riders/available` - List available riders

### Riders
- `GET /api/rider/deliveries` - Get assigned deliveries
- `POST /api/rider/location` - Update current location
- `PUT /api/rider/availability` - Toggle availability

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Retailer   │────▶│   Flask     │◀────│  Dispatcher │
│   (PWA)     │     │   Backend   │     │   (PWA)     │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  WebSocket   │
                    │   Server     │
                    └──────┬──────┘
                           │
                     ┌─────┴─────┐
                     │   Rider   │
                     │   (PWA)   │
                     └───────────┘
```

## Status Flow

```
PENDING → ASSIGNED → PICKED_UP → IN_TRANSIT → DELIVERED
   ↓          ↓           ↓            ↓
CANCELLED   FAILED ←─────┴────────────┘
```

## Production Deployment

See the deployment guide in the project documentation for:
- VPS setup (DigitalOcean/Linode/AWS)
- Nginx reverse proxy configuration
- SSL with Let's Encrypt
- PostgreSQL migration
- Supervisor process management

## License

MIT License

## Contributing

Contributions welcome! Please open an issue or pull request.
