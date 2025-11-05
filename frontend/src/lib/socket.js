import { io } from 'socket.io-client';

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
});

/**
 * Connects to the WebSocket server.
 */
export const connectSocket = () => {
  if (socket.connected) {
    return;
  }
  console.log(`Attempting socket connection to origin with path /socket.io`);
  socket.connect();
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
 * Joins a specific room for a model run.
 */
export const joinTrainingRoom = (modelRunId) => {
  const token = localStorage.getItem('access_token');
  if (!token) {
    console.error("No auth token found, cannot join room.");
    return;
  }

  console.log(`Attempting to join room: ${modelRunId}`); // Added log
  socket.emit('join_room', {
    token: token,
    model_run_id: modelRunId,
  });
};

/**
 * Leaves a specific room.
 */
export const leaveTrainingRoom = (modelRunId) => {
  console.log(`Leaving room: ${modelRunId}`); // Added log
  socket.emit('leave_room', { model_run_id: modelRunId });
};

// Add listeners for debugging connection
socket.on('connect', () => {
  console.log('Socket connected successfully:', socket.id);
});

socket.on('disconnect', (reason) => {
  console.log('Socket disconnected:', reason);
});

socket.on('connect_error', (err) => {
  console.error('Socket connection error:', err.message, err.cause);
});

export default socket;