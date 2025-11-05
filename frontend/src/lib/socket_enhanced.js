import { io } from 'socket.io-client';

// Enhanced socket functionality with better error handling

// Get the base URL (origin) - VITE_WS_URL is now just "/" or empty
const WS_URL = '/'; // Connect relative to the current origin

const socket = io(WS_URL, {
    // Explicitly specify transports, starting with websocket
    transports: ['websocket', 'polling'],
    path: '/socket.io', // Nginx routes this path
    autoConnect: false,
    withCredentials: true,
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 20000,
});

/**
 * Connects to the WebSocket server.
 */
export const connectSocket = () => {
    if (socket.connected) {
        return Promise.resolve(socket);
    }

    return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
            reject(new Error('Socket connection timeout'));
        }, 10000);

        socket.on('connect', () => {
            clearTimeout(timeout);
            console.log('Socket connected successfully:', socket.id);
            resolve(socket);
        });

        socket.on('connect_error', (err) => {
            clearTimeout(timeout);
            reject(new Error(`Socket connection failed: ${err.message}`));
        });

        console.log(`Attempting socket connection to origin with path /socket.io`);
        socket.connect();
    });
};

/**
 * Disconnects from the WebSocket server.
 */
export const disconnectSocket = () => {
    if (socket.connected) {
        socket.disconnect();
    }
};

/**
 * Enhanced room joining with error handling and Promise support
 */
export const joinTrainingRoom = (modelRunId) => {
    return new Promise((resolve, reject) => {
        const token = localStorage.getItem('access_token');
        if (!token) {
            reject(new Error("No auth token found, cannot join room."));
            return;
        }

        console.log(`Attempting to join room: ${modelRunId}`);

        // Set up one-time listener for join confirmation
        const onRoomJoined = (data) => {
            if (data.model_run_id === modelRunId || data.room === modelRunId) {
                socket.off('room_joined', onRoomJoined);
                socket.off('room_error', onRoomError);
                console.log(`Successfully joined room: ${modelRunId}`);
                resolve(data);
            }
        };

        const onRoomError = (error) => {
            if (error.model_run_id === modelRunId || error.room === modelRunId) {
                socket.off('room_joined', onRoomJoined);
                socket.off('room_error', onRoomError);
                reject(new Error(error.message || 'Failed to join room'));
            }
        };

        socket.on('room_joined', onRoomJoined);
        socket.on('room_error', onRoomError);

        // Set timeout for room joining
        const timeout = setTimeout(() => {
            socket.off('room_joined', onRoomJoined);
            socket.off('room_error', onRoomError);
            reject(new Error('Room joining timeout after 10 seconds'));
        }, 10000);

        // Join the room
        socket.emit('join_room', {
            token: token,
            model_run_id: modelRunId,
        });

        // Handle case where room is joined immediately
        socket.on('room_joined', () => clearTimeout(timeout));
    });
};

/**
 * Leaves a specific room.
 */
export const leaveTrainingRoom = (modelRunId) => {
    console.log(`Leaving room: ${modelRunId}`);
    socket.emit('leave_room', { model_run_id: modelRunId });
};

// Add listeners for debugging connection
socket.on('disconnect', (reason) => {
    console.log('Socket disconnected:', reason);
    // Handle reconnection logic
    if (reason === 'io server disconnect') {
        // Server disconnected, don't reconnect automatically
        socket.connect();
    }
});

socket.on('connect_error', (err) => {
    console.error('Socket connection error:', err.message, err.cause);
    // Handle specific error cases
    if (err.message.includes('Authentication error')) {
        console.warn('Socket authentication failed, clearing token');
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
    }
});

// Socket connection status helpers
export const isSocketConnected = () => socket.connected;
export const getSocketId = () => socket.id;

export default socket;