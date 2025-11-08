import { io } from 'socket.io-client';

let socket;

const WS_URL = '/';

const getSocket = () => {
    if (!socket) {
        socket = io(WS_URL, {
            transports: ['websocket', 'polling'],
            path: '/socket.io',
            autoConnect: false,
            withCredentials: true,
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            timeout: 20000,
        });

        // Add logging for socket events
        socket.on('connect', () => console.log('Socket connected:', socket.id));
        socket.on('disconnect', (reason) => console.log('Socket disconnected:', reason));
        socket.on('connect_error', (err) => console.error('Socket connection error:', err.message));
    }
    return socket;
};

export const connectSocket = () => {
    const s = getSocket();
    if (!s.connected) {
        s.connect();
    }
};

/**
 * Disconnects from the WebSocket server.
 */
export const disconnectSocket = () => {
    const s = getSocket();
    if (s.connected) {
        s.disconnect();
    }
};

/**
 * Enhanced room joining with error handling and Promise support
 */
export const joinTrainingRoom = (modelRunId) => {
    const s = getSocket();
    return new Promise((resolve, reject) => {
        const token = localStorage.getItem('access_token');
        if (!token) {
            return reject(new Error("No auth token found, cannot join room."));
        }

        s.emit('join_room', { token: token, model_run_id: modelRunId }, (ack) => {
            if (ack.success) {
                console.log(`Successfully joined room: ${modelRunId}`);
                resolve(ack);
            } else {
                console.error(`Failed to join room: ${ack.error}`);
                reject(new Error(ack.error || 'Failed to join room'));
            }
        });
    });
};

/**
 * Leaves a specific room.
 */
export const leaveTrainingRoom = (modelRunId) => {
    const s = getSocket();
    if (s.connected) {
        s.emit('leave_room', { model_run_id: modelRunId });
    }
};

// Socket connection status helpers
export const isSocketConnected = () => getSocket().connected;
export const getSocketId = () => getSocket().id;

export default getSocket();