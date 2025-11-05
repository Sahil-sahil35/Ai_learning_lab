import eventlet
# We must monkey-patch for eventlet to work with SocketIO
eventlet.monkey_patch()

from app import create_app, socketio
import os

app = create_app(os.getenv('FLASK_CONFIG') or 'default')

if __name__ == '__main__':
    print("Starting Flask-SocketIO server with eventlet...")
    socketio.run(app, host='0.0.0.0', port=5000)