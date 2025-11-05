import React from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faChartLine, faChartBar, faBrain } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';
import styles from './MetricCard.module.css'; // Import CSS Module

const MetricCard = ({ label, value, format = 'number', icon, color = 'blue' }) => {
  // Format the value based on format type
  let formattedValue = value;

  if (value === null || value === undefined) {
    formattedValue = 'N/A';
  } else if (typeof value === 'number') {
    if (format === 'percent') {
      formattedValue = `${(value * 100).toFixed(1)}%`;
    } else if (format === 'decimal') {
      formattedValue = value.toFixed(4);
    } else if (format === 'currency') {
      formattedValue = value.toLocaleString('en-US', {
        style: 'currency',
        currency: 'USD'
      });
    } else if (format === 'time') {
      formattedValue = value.toFixed(2) + 's';
    } else {
      formattedValue = String(value);
    }
  } else {
    formattedValue = String(value);
  }

  // Get the appropriate icon
  const getIcon = () => {
    if (icon) return <FontAwesomeIcon icon={icon} />;
    if (format === 'percent' || format === 'decimal') return <FontAwesomeIcon icon={faChartLine} />;
    if (label.toLowerCase().includes('accuracy') || label.toLowerCase().includes('r2')) return <FontAwesomeIcon icon={faChartBar} />;
    return <FontAwesomeIcon icon={faBrain} />;
  };

  // Get color based on value type and format
  const getColorClass = () => {
    if (color !== 'blue') return styles[color];
    if (format === 'percent') {
      if (value >= 0.9) return styles.excellent;
      if (value >= 0.7) return styles.good;
      if (value >= 0.5) return styles.average;
      return styles.poor;
    }
    if (format === 'decimal' && typeof value === 'number') {
      if (Math.abs(value) >= 0.9) return styles.excellent;
      if (Math.abs(value) >= 0.7) return styles.good;
      if (Math.abs(value) >= 0.5) return styles.average;
      return styles.poor;
    }
    return styles.default;
  };

  // Check if this is a placeholder value
  const isPlaceholder = value === null || value === undefined || (typeof value === 'string' && (value.includes('N/A') || value.includes('N/A')));

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`${styles.metricCard} ${getColorClass()} ${isPlaceholder ? styles.placeholder : ''}`}
    >
      <div className={styles.metricIcon}>
        {getIcon()}
      </div>
      <div className={styles.metricContent}>
        <div className={styles.metricLabel}>{label}</div>
        <div className={styles.metricValue}>{formattedValue}</div>
        {isPlaceholder && (
          <div className={styles.placeholderText}>No data available</div>
        )}
      </div>
    </motion.div>
  );
};

export default MetricCard;