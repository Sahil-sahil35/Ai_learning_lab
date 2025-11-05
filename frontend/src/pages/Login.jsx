import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faBrain, faEnvelope, faLock } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import api from '../lib/api';
import useAuthStore from '../lib/auth';
import styles from './AuthForm.module.css'; // Use a shared AuthForm style

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const loginAction = useAuthStore((state) => state.login); // Renamed variable

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error('Please enter both email and password.');
      return;
    }
    setIsLoading(true);

    try {
      const response = await api.post('/auth/login', { email, password });
      const { access_token } = response.data;

      loginAction(access_token); // Use renamed variable
      toast.success('Login successful! Redirecting...');

      // Redirect to the dashboard
      navigate('/dashboard');

    } catch (error) {
      const errorMsg = error.response?.data?.msg || 'Login failed. Please check your credentials.';
      toast.error(errorMsg);
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.authPageContainer}>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className={styles.authFormCard}
      >
        <div className={styles.formHeader}>
          <FontAwesomeIcon icon={faBrain} className={styles.headerIcon} />
          <h1 className={styles.formTitle}>Welcome Back!</h1>
          <p className={styles.formSubtitle}>Log in to your ML LearnLab account.</p>
        </div>

        <form className={styles.form} onSubmit={handleSubmit}>
          {/* Email Field */}
          <div className={styles.inputGroup}>
            <label htmlFor="email" className={styles.label}>Email Address</label>
            <div className={styles.inputWrapper}>
              <FontAwesomeIcon icon={faEnvelope} className={styles.inputIcon} />
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className={styles.inputField}
                placeholder="you@example.com"
              />
            </div>
          </div>

          {/* Password Field */}
          <div className={styles.inputGroup}>
            <label htmlFor="password" className={styles.label}>Password</label>
            <div className={styles.inputWrapper}>
              <FontAwesomeIcon icon={faLock} className={styles.inputIcon} />
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className={styles.inputField}
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className={styles.submitButton}
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <p className={styles.footerText}>
          Don't have an account?{' '}
          <Link to="/signup" className={styles.footerLink}>
            Sign up
          </Link>
        </p>
      </motion.div>
    </div>
  );
};

export default Login;