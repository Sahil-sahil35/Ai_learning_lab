// frontend/src/components/StepIndicator.jsx
import React from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCheck } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';
import styles from './StepIndicator.module.css';

const steps = [
  "Select Model",
  "Upload Data",
  "Analyze",
  "Clean",
  "Configure",
  "Train",
  "Results"
];

const StepIndicator = ({ currentStep }) => {
  const currentIndex = steps.indexOf(currentStep);


  return (
    <nav className={styles.stepNav} aria-label="Progress">
      <ol className={styles.stepList}>
        {steps.map((step, index) => {
          const isCompleted = index < currentIndex;
          const isActive = index === currentIndex;
          const isUpcoming = index > currentIndex;

          let statusClass = styles.upcomingStep;
          if (isCompleted) statusClass = styles.completedStep;
          if (isActive) statusClass = styles.activeStep;

          return (
            <li key={step} className={styles.stepItem}>
              <motion.div
                initial={{ scale: 0.8 }}
                animate={{ scale: 1 }}
                className={styles.stepContent}
              >
                <div className={`${styles.stepCircle} ${statusClass}`}>
                  {isCompleted ? <FontAwesomeIcon icon={faCheck} /> : index + 1}
                </div>
                <p className={`${styles.stepLabel} ${isActive || isCompleted ? styles.stepLabelActive : ''}`}>
                  {step}
                </p>
              </motion.div>

              {index < steps.length - 1 && (
                <div className={`${styles.connector} ${isCompleted ? styles.connectorCompleted : ''}`} />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};

export default StepIndicator;