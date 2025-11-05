import React from 'react';
import Navbar from './Navbar';
import styles from './Layout.module.css'; // Import CSS Module

// Removed Sidebar import for now

const Layout = ({ children }) => {
  return (
    <div className={styles.layoutContainer}>
      <Navbar />
      <div className={styles.contentWrapper}>
        {/* Sidebar placeholder */}
        {/* <aside className={styles.sidebar}>Sidebar Area</aside> */}
        <main className={styles.mainContent}>
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;