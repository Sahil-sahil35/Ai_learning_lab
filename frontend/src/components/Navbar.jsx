import React, { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faBrain, faUser, faCog, faSignOutAlt, faChevronDown } from '@fortawesome/free-solid-svg-icons';
import { motion, AnimatePresence } from 'framer-motion';
import useAuthStore from '../lib/auth';
import styles from './Navbar.module.css'; // Import the new CSS Module

const Navbar = () => {
  const { user, logout } = useAuthStore((state) => ({
    user: state.user,
    logout: state.logout,
  }));

  const [isMenuOpen, setIsMenuOpen] = useState(false);

  // Framer Motion animation variants (keep)
  const menuVariants = {
    hidden: { opacity: 0, scale: 0.95, y: -10 },
    visible: { opacity: 1, scale: 1, y: 0 },
    exit: { opacity: 0, scale: 0.95, y: -10 },
  };

  return (
    <header className={styles.navbar}> {/* Use header tag */}
      <div className={styles.navContent}> {/* Wrapper for content alignment */}

        {/* --- Left Side: Logo & Main Nav --- */}
        <div className={styles.navLeft}>
          {/* Logo */}
          <Link to="/dashboard" className={styles.brand}>
            <FontAwesomeIcon icon={faBrain} className={styles.brandIcon} />
            <span className={styles.brandName}>ML LearnLab</span>
          </Link>

          {/* Main Navigation */}
          <nav className={styles.mainNav}>
            <NavLink
              to="/dashboard"
              className={({ isActive }) =>
                `${styles.navItem} ${isActive ? styles.navItemActive : ''}`
              }
            >
              Dashboard
            </NavLink>
            {/* Add more links like <NavLink to="/models" className={...}>Models</NavLink> */}
          </nav>
        </div>

        {/* --- Right Side: User Menu --- */}
        <div className={styles.navRight}>
          <div className={styles.userMenu}> {/* Container for positioning dropdown */}
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className={styles.userButton}
              aria-expanded={isMenuOpen}
              aria-haspopup="true"
            >
              <div className={styles.avatar}>
                <span>
                  {user?.username ? user.username[0].toUpperCase() : <FontAwesomeIcon icon={faUser} />}
                </span>
              </div>
              <span className={styles.usernameDisplay}>{user?.username}</span>
              <FontAwesomeIcon icon={faChevronDown} className={styles.userButtonChevron} />
            </button>

            {/* Dropdown Menu with Animation */}
            <AnimatePresence>
              {isMenuOpen && (
                <motion.div
                  variants={menuVariants}
                  initial="hidden"
                  animate="visible"
                  exit="exit"
                  transition={{ duration: 0.15 }}
                  className={styles.dropdown}
                  role="menu"
                >
                  <div className={styles.dropdownHeader} role="none">
                    Signed in as <br />
                    <strong>{user?.email}</strong>
                  </div>
                  <Link
                    to="/settings" // Future page
                    className={styles.dropdownLink}
                    onClick={() => setIsMenuOpen(false)}
                    role="menuitem"
                  >
                    <FontAwesomeIcon icon={faCog} fixedWidth /> {/* fixedWidth for alignment */}
                    <span>Settings</span>
                  </Link>
                  <button
                    onClick={logout}
                    className={`${styles.dropdownLink} ${styles.logout}`}
                    role="menuitem"
                  >
                    <FontAwesomeIcon icon={faSignOutAlt} fixedWidth />
                    <span>Logout</span>
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Navbar;