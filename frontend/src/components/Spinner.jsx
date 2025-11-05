import React from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSpinner } from '@fortawesome/free-solid-svg-icons';
import styles from './Spinner.module.css'; // Import CSS Module

const Spinner = ({ fullPage = false, size = 'medium' }) => {
  // Determine icon size class based on prop
  const sizeClass = size === 'large' ? styles.iconLarge : styles.iconMedium;

  if (fullPage) {
    return (
      <div className={styles.fullPageSpinner}>
        <FontAwesomeIcon icon={faSpinner} spin className={sizeClass} />
      </div>
    );
  }

  // Inline spinner with optional sizing
  return (
    <div className={styles.inlineSpinner}>
      <FontAwesomeIcon icon={faSpinner} spin className={sizeClass} />
    </div>
  );
};

export default Spinner;