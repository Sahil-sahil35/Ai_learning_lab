import React from 'react';
import { Link } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faBrain, faPlayCircle, faUserPlus, faSignInAlt, faChartLine, faProjectDiagram, faEye } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';
import styles from './Home.module.css'; // Import the CSS Module

const Home = () => {
  return (
    <div className={styles.homeContainer}>
      {/* --- Navigation --- */}
      <nav className={styles.homeNav}>
        <div className={styles.navContent}>
          <Link to="/" className={styles.brand}>
            <FontAwesomeIcon icon={faBrain} className={styles.brandIcon} />
            <span className={styles.brandName}>ML LearnLab</span>
          </Link>
          <div className={styles.authButtons}>
            <Link to="/login" className={`${styles.button} ${styles.loginButton}`}>
              <FontAwesomeIcon icon={faSignInAlt} />
              <span>Login</span>
            </Link>
            <Link to="/signup" className={`${styles.button} ${styles.signupButton}`}>
              <FontAwesomeIcon icon={faUserPlus} />
              <span>Sign Up</span>
            </Link>
          </div>
        </div>
      </nav>

      {/* --- Hero Section --- */}
      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8 }}
        className={styles.heroSection}
      >
        <motion.h1
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className={styles.heroTitle}
        >
          Learn AI/ML Interactively
        </motion.h1>
        <motion.p
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.5 }}
          className={styles.heroSubtitle}
        >
          Master machine learning by building, training, and visualizing models step-by-step. Go from data upload to insightful results with our guided platform.
        </motion.p>
        <motion.div
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.6, duration: 0.5 }}
          className={styles.heroActions}
        >
          <Link
            to="/signup"
            className={`${styles.button} ${styles.ctaButton}`}
          >
            Get Started Free
          </Link>
          <button className={`${styles.button} ${styles.secondaryButton}`}>
            <FontAwesomeIcon icon={faPlayCircle} />
            <span>Watch Demo</span>
          </button>
        </motion.div>
      </motion.section>

      {/* --- Features Section --- */}
      <section className={styles.featuresSection}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>Why ML LearnLab?</h2>
          <p className={styles.sectionSubtitle}>
            Our platform simplifies the complex world of machine learning, making it accessible through hands-on experience and clear visualizations.
          </p>
        </div>
        <div className={styles.featuresGrid}>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className={styles.featureCard}>
            <FontAwesomeIcon icon={faProjectDiagram} className={`${styles.featureIcon} ${styles.iconPrimary}`} />
            <h3 className={styles.featureTitle}>Step-by-Step Workflow</h3>
            <p className={styles.featureDescription}>Guided process from data upload, cleaning, configuration, training, to results analysis.</p>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className={styles.featureCard}>
            <FontAwesomeIcon icon={faEye} className={`${styles.featureIcon} ${styles.iconSuccess}`} />
            <h3 className={styles.featureTitle}>Live Visualizations</h3>
            <p className={styles.featureDescription}>Watch your model learn in real-time with dynamic charts and metrics updates.</p>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className={styles.featureCard}>
            <FontAwesomeIcon icon={faChartLine} className={`${styles.featureIcon} ${styles.iconAccent}`} />
            <h3 className={styles.featureTitle}>Insightful Results</h3>
            <p className={styles.featureDescription}>Understand model performance through comprehensive metrics, plots, and educational summaries.</p>
          </motion.div>
        </div>
      </section>

      {/* --- Footer --- */}
      <footer className={styles.footer}>
        <p>
          &copy; {new Date().getFullYear()} ML LearnLab. All rights reserved.
        </p>
      </footer>
    </div>
  );
};

export default Home;