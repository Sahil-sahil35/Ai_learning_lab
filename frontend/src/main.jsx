import React from 'react';
import ReactDOM from 'react-dom/client';
import { Toaster } from 'react-hot-toast';
import { BrowserRouter } from 'react-router-dom'; // <-- 1. IMPORT THIS

import App from './App';
import './index.css';

// Initialize app before rendering
const initializeApp = async () => {
  try {
    const { default: useAuthStore } = await import('./lib/auth');
    // Initialize auth state from localStorage
    useAuthStore.getState().initializeAuth();
  } catch (error) {
    console.error('Failed to initialize app:', error);
  }
};

// Initialize app and then render
initializeApp().then(() => {
  ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <BrowserRouter> {/* <-- 2. ADD THIS WRAPPER */}
        <App />
        <Toaster
          position="top-center"
          reverseOrder={false}
          toastOptions={{
            className: '',
            style: {
              background: '#374151', // var(--gray-700)
              color: '#F9FAFB',     // var(--gray-50)
              border: '1px solid #4B5563', // var(--gray-600)
            },
          }}
        />
      </BrowserRouter> {/* <-- 3. CLOSE THE WRAPPER */}
    </React.StrictMode>,
  );
});