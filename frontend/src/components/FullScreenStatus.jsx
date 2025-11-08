// frontend/src/components/FullScreenStatus.jsx
import React from 'react';
import { Link } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faExclamationCircle, faArrowLeft } from '@fortawesome/free-solid-svg-icons';
import Spinner from './Spinner';
import styles from './FullScreenStatus.module.css';

const FullScreenStatus = ({ isLoading, error, loadingMessage = 'Loading...', backLink = '/dashboard' }) => {
    if (isLoading) {
        return (
            <div className={styles.centeredState}>
                <Spinner size="large" />
                <p>{loadingMessage}</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className={`${styles.centeredState} ${styles.errorState}`}>
                <FontAwesomeIcon icon={faExclamationCircle} size="3x" />
                <p>{error}</p>
                <Link to={backLink} className={styles.backLink}>
                    <FontAwesomeIcon icon={faArrowLeft} /> Back to Dashboard
                </Link>
            </div>
        );
    }

    return null;
};

export default FullScreenStatus;
