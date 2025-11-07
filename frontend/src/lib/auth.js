import { create } from 'zustand';
import { jwtDecode } from 'jwt-decode';
import api from './api';

/**
 * Zustand store for authentication.
 * This provides a global state for the user, access token,
 * and helper functions (login, logout, loadUser) that can be
 * accessed from any component in the app.
 */
const useAuthStore = create((set, get) => ({
  user: JSON.parse(localStorage.getItem('user')) || null,
  accessToken: localStorage.getItem('access_token') || null,
  isLoading: false,
  isAuthenticated: false,
  
  /**
   * Logs in the user.
   * @param {string} token - The JWT access token.
   */
  login: (token) => {
    try {
      // Decode the token to get user info (if needed)
      // Note: We primarily rely on the /api/auth/me endpoint
      const decoded = jwtDecode(token);
      
      // Store token
      localStorage.setItem('access_token', token);
      set({ accessToken: token });

      // Fetch user profile
      get().loadUser();
      
    } catch (error) {
      console.error("Failed to decode token:", error);
      get().logout();
    }
  },

  /**
   * Fetches the user's profile from the /me endpoint and stores it.
   */
  loadUser: async () => {
    try {
      set({ isLoading: true });
      const response = await api.get('/auth/me');
      const user = response.data;
      localStorage.setItem('user', JSON.stringify(user));
      set({ user: user, isAuthenticated: true, isLoading: false });
    } catch (error) {
      console.error("Failed to load user:", error);
      set({ isLoading: false });
      // If we can't fetch the user, the token is bad. Log out.
      get().logout();
    }
  },

  /**
   * Logs out the user.
   */
  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false });
    // Redirect to login
    window.location.href = '/login';
  },

  /**
   * Initialize authentication state from localStorage.
   */
  initializeAuth: () => {
    const token = localStorage.getItem('access_token');
    const user = JSON.parse(localStorage.getItem('user'));

    if (token && user) {
      set({
        accessToken: token,
        user: user,
        isAuthenticated: true,
        isLoading: false
      });
    } else {
      set({
        accessToken: null,
        user: null,
        isAuthenticated: false,
        isLoading: false
      });
    }
  },

  /**
   * Check if user has specific role.
   */
  hasRole: (role) => {
    const user = get().user;
    return user && user.role === role;
  },

  /**
   * Check if user has admin privileges.
   */
  isAdmin: () => {
    const user = get().user;
    return user && (user.role === 'admin' || user.role === 'super_admin');
  }


}));

export default useAuthStore;

