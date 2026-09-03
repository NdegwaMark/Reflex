from app import app, socketio, create_default_data

create_default_data()

if __name__ == "__main__":
    socketio.run(app)
