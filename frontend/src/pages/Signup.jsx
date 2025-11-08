import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faBrain, faEnvelope, faLock, faUser } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import api from '../lib/api';
import useAuthStore from '../lib/auth';
import styles from './AuthForm.module.css'; // Use the same shared AuthForm style

const Signup = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const loginAction = useAuthStore((state) => state.login); // Renamed variable

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !email || !password) {
      toast.error('Please fill in all fields.');
      return;
    }
    if (password.length < 8) {
      toast.error('Password must be at least 8 characters long.');
      return;
    }
    setIsLoading(true);

    try {
      const response = await api.post('/auth/signup', { username, email, password });
      // const { access_token } = response.data;
       toast.success('Account created successfully! Please log in.');

      // loginAction(access_token); // Use renamed variable
      // toast.success('Account created! Redirecting...');

      // navigate('/dashboard');
      // Redirect to login page after successful signup
      setTimeout(() => {
        navigate('/login');
      }, 1500);

    } catch (error) {
      const errorMsg = error.response?.data?.msg || 'Sign up failed. Please try again.';
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
          <h1 className={styles.formTitle}>Create Your Account</h1>
          <p className={styles.formSubtitle}>Start your ML journey today.</p>
        </div>

        <form className={styles.form} onSubmit={handleSubmit}>
          {/* Username Field */}
          <div className={styles.inputGroup}>
            <label htmlFor="username" className={styles.label}>Username</label>
            <div className={styles.inputWrapper}>
              <FontAwesomeIcon icon={faUser} className={styles.inputIcon} />
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className={styles.inputField}
                placeholder="your_username"
              />
            </div>
          </div>

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
                placeholder="Min. 8 characters"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className={styles.submitButton}
          >
            {isLoading ? 'Creating Account...' : 'Sign Up'}
          </button>
        </form>

        <p className={styles.footerText}>
          Already have an account?{' '}
          <Link to="/login" className={styles.footerLink}>
            Log in
          </Link>
        </p>
      </motion.div>
    </div>
  );
};

export default Signup;