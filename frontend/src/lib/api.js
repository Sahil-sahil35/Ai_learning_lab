import axios from 'axios';

// Get the API URL from environment variables set by Vite
const VITE_API_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: VITE_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request interceptor.
 * This function is called before every request.
 * It dynamically adds the Authorization header.
 */
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor.
 * This can be used to handle 401 (Unauthorized) errors globally,
 * for example, by redirecting to the login page.
 */
api.interceptors.response.use(
  (response) => {
    // Any status code that lies within the range of 2xx
    return response;
  },
  (error) => {
    console.error('API Error:', error);

    // Handle 401 errors, e.g., token expired
    if (error.response && error.response.status === 401) {
      console.error("Unauthorized. Token may be invalid or expired.");
      // Clear local storage and redirect to login
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      // Use window.location to force a full page reload for auth state
      window.location.href = '/login';
    }

    // Handle network errors
    if (!error.response) {
      console.error("Network error. Please check your connection.");
      error.message = "Network error. Please check your connection and try again.";
    }

    // Handle server errors
    if (error.response && error.response.status >= 500) {
      console.error("Server error. Please try again later.");
      error.message = "Server error. Please try again later.";
    }

    return Promise.reject(error);
  }
);

/**
 * Request retry helper for failed requests
 */
export const retryRequest = async (requestFn, maxRetries = 3) => {
  let lastError;

  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn();
    } catch (error) {
      lastError = error;
      console.warn(`Request failed (attempt ${i + 1}/${maxRetries}):`, error);

      // Don't retry on auth errors or client errors
      if (error.response && (error.response.status === 401 || error.response.status < 500)) {
        throw error;
      }

      // Wait before retrying (exponential backoff)
      if (i < maxRetries - 1) {
        await new Promise(resolve => setTimeout(resolve, Math.pow(2, i) * 1000));
      }
    }
  }

  throw lastError;
};

export default api;