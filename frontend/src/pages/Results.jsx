// frontend/src/pages/Results.jsx

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSpinner, faExclamationCircle, faCheckCircle, faDownload, faFileAlt, faBrain, faChartBar, faArrowLeft } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';

import StepIndicator from '../components/StepIndicator';
import MetricCard from '../components/charts/MetricCard';
import api from '../lib/api';
import Spinner from '../components/Spinner';
import FullScreenStatus from '../components/FullScreenStatus';
import styles from './Results.module.css';

// --- Helpers (Keep as before) ---
const formatMetricLabel = (key) => key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
const formatTime = (seconds) => { /* ... keep implementation ... */
  if (seconds === null || seconds === undefined) return 'N/A';
  if (seconds < 1) return `< 1 sec`; // Handle very short times
  seconds = Math.round(seconds); // Round to nearest second for display
  if (seconds < 60) return `${seconds} sec`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes} min ${remainingSeconds} sec`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours} hr ${remainingMinutes} min`;
};
// --- End Helpers ---


const Results = () => {
  const { runId } = useParams();
  const [runDetails, setRunDetails] = useState(null); // Stores the ModelRun object
  const [resultsData, setResultsData] = useState(null); // Stores { metrics, summary, files }
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // --- Metric Display Config (Keep as is) ---
  const metricDisplayConfig = {
      // Classification
      'accuracy': { label: 'Accuracy', format: 'percent' },
      'roc_auc': { label: 'AUC', format: 'decimal' },
      'precision': { label: 'Precision', format: 'percent' },
      'recall': { label: 'Recall', format: 'percent' },
      'f1-score': { label: 'F1 Score', format: 'decimal' }, // Handle potential hyphen
      'f1_score': { label: 'F1 Score', format: 'decimal' }, // Handle potential underscore
      'log_loss': { label: 'Log Loss', format: 'decimal' },
      // Regression
      'r2_score': { label: 'R² Score', format: 'decimal' },
      'rmse': { label: 'RMSE', format: 'decimal' },
      'mae': { label: 'MAE', format: 'decimal' },
      'explained_variance': { label: 'Explained Var.', format: 'percent'},
      // Generic / Training Specific
      'final_val_loss': { label: 'Final Val Loss', format: 'decimal' },
      'final_train_loss': { label: 'Final Train Loss', format: 'decimal' },
      // Skip complex objects
      'classification_report': { skip: true },
      'confusion_matrix': { skip: true },
      'precision_recall_curve': { skip: true }
  };


  // --- FIX: Fetch Real Data ---
  useEffect(() => {
    const fetchAllData = async () => {
      setIsLoading(true);
      setError(null);
      setRunDetails(null); // Clear previous state
      setResultsData(null); // Clear previous state
      try {
        const response = await api.get(`/training/run/${runId}/results`);
        
        // Basic validation of response structure
        if (!response.data || !response.data.run || !response.data.results) {
             throw new Error("Incomplete data received from server.");
        }

        setRunDetails(response.data.run);
        setResultsData(response.data.results);

        if (response.data.run.status !== 'SUCCESS') {
           setError(`Training status is ${response.data.run.status}. Results may be incomplete or indicate a failure.`);
           // Keep data loaded even if status isn't success, to show partial info/logs if available
        }

      } catch (err) {
        console.error("Error fetching results:", err);
        const errorMsg = err.response?.data?.msg || "Failed to load results. The run may not exist or an error occurred.";
        setError(errorMsg);
        // Ensure state is cleared on error
        setResultsData(null);
        setRunDetails(null);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAllData();
  }, [runId]);
  // --- END FIX ---

  // --- FIX: Update getFileUrl ---
  const getFileUrl = (filename) => {
    // Use the new backend endpoint
    return `/api/training/run/${runId}/file/${encodeURIComponent(filename)}`;
  };
  // --- END FIX ---


  // --- Loading and Error States ---
  if (isLoading || (error && !runDetails && !resultsData)) {
    return <FullScreenStatus isLoading={isLoading} error={error} loadingMessage="Loading results..." />;
  }

  // --- Handle case where run exists but no results (e.g., failed run) ---
   if (!resultsData || (!resultsData.metrics && !resultsData.summary && !resultsData.files)) {
       // Check run status for a better message
       const statusMsg = runDetails ? `Run status: ${runDetails.status}.` : "Run details unavailable.";
        return (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <StepIndicator currentStep="Results" />
               <div className={`${styles.banner} ${styles.warningBanner}`}>
                 <FontAwesomeIcon icon={faExclamationCircle} />
                 <div>
                   <h1>Results Unavailable</h1>
                   <p>{error || `No results data found for this run. ${statusMsg}`}</p>
                 </div>
               </div>
               <div className={styles.centeredState}>
                    <Link to="/dashboard" className={styles.backLink}>
                      <FontAwesomeIcon icon={faArrowLeft} /> Back to Dashboard
                    </Link>
               </div>
          </motion.div>
        );
   }


  // --- Destructure results data (Keep safe defaults) ---
  const { metrics = {}, summary = {}, files = [] } = resultsData;
  const visualizations = files.filter(f => f.endsWith('.png') || f.endsWith('.html') || f.endsWith('.svg'));
  const downloadableFiles = files.filter(f => !visualizations.includes(f));
  const primaryMetrics = Object.entries(metrics)
      .filter(([key, value]) => metricDisplayConfig[key] && !metricDisplayConfig[key].skip && value !== null && value !== undefined)
      .sort(([keyA], [keyB]) => { // Optional: Sort metrics for consistency
          const order = ['accuracy', 'r2_score', 'rmse', 'mae', 'precision', 'recall', 'f1_score', 'roc_auc'];
          return (order.indexOf(keyA) === -1 ? 99 : order.indexOf(keyA)) - (order.indexOf(keyB) === -1 ? 99 : order.indexOf(keyB));
       });


  // --- Main Render Logic (Keep similar structure) ---
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <StepIndicator currentStep="Results" />

      {/* --- Status Banner --- */}
      {runDetails.status === 'SUCCESS' ? (
         <div className={`${styles.banner} ${styles.successBanner}`}>
           <FontAwesomeIcon icon={faCheckCircle} />
           <div>
             <h1>Training Successful!</h1>
             <p>Model <strong>{summary?.model_type || runDetails.model_id_str}</strong> completed training successfully.</p>
             <p>View the performance metrics and download model artifacts below.</p>
           </div>
         </div>
      ) : ( // Show warning banner if run exists but status isn't SUCCESS
         <div className={`${styles.banner} ${styles.warningBanner}`}>
           <FontAwesomeIcon icon={faExclamationCircle} />
           <div>
             <h1>Training Status: {runDetails.status}</h1>
             <p>{error || 'Results may be incomplete or reflect a failed run.'}</p>
             {runDetails.status === 'FAILED' && (
               <p>Please check the training logs for error details.</p>
             )}
             {runDetails.status === 'ANALYSIS_FAILED' && (
               <p>Data analysis failed. Please check your data format and try again.</p>
             )}
             {runDetails.status === 'CLEANING_FAILED' && (
               <p>Data cleaning failed. Review cleaning options and data quality.</p>
             )}
           </div>
         </div>
      )}

      {/* --- Main Grid --- */}
      <div className={styles.mainGrid}>
        <div className={styles.leftColumn}>
          {/* --- Metrics Section --- */}
          {primaryMetrics.length > 0 ? (
            <section className={styles.card}>
              <h2>Final Performance Metrics</h2>
              <div className={styles.metricsGrid}>
                {primaryMetrics.map(([key, value]) => {
                  const config = metricDisplayConfig[key.toLowerCase()] || {}; // Use lowercase key for matching config
                  return (
                    <MetricCard
                      key={key}
                      label={config.label || formatMetricLabel(key)}
                      value={value}
                      format={config.format || (typeof value === 'number' && value < 1.1 && value > -0.1 ? 'decimal' : 'number')} // Basic format guess
                    />
                  );
                })}
              </div>
              {/* TODO: Add Classification Report table if metrics.classification_report */}
              {metrics.classification_report && typeof metrics.classification_report === 'object' && (
                   <div className={styles.classificationReport}> {/* Add styling */}
                       <h3>Classification Report</h3>
                       {/* Render table here */}
                   </div>
              )}
               {metrics.confusion_matrix && Array.isArray(metrics.confusion_matrix) && (
                   <div className={styles.confusionMatrix}> {/* Add styling */}
                       <h3>Confusion Matrix</h3>
                       {/* Render CM here */}
                   </div>
               )}
            </section>
          ) : (
            <section className={styles.card}>
                 <h2>Final Performance Metrics</h2>
                 <p className={styles.noDataText}>No final metrics were found for this run.</p>
            </section>
          )}

          {/* --- Visualizations Section --- */}
          {visualizations.length > 0 ? (
            <section className={styles.card}>
              <h2>Visualizations</h2>
              <div className={styles.visualizationsGrid}>
                {visualizations.map((file) => (
                  <div key={file} className={styles.vizItem}>
                    <h3>{formatMetricLabel(file.split('.')[0])}</h3>
                    <div className={styles.vizContent}>
                      {file.endsWith('.html') ? (
                        // Add sandbox attribute for security
                        <iframe src={getFileUrl(file)} title={file} className={styles.vizIframe} sandbox="allow-scripts allow-same-origin"></iframe>
                      ) : (
                       <img src={getFileUrl(file)} alt={file} className={styles.vizImage} loading="lazy" />
                      )}
                      {(file.endsWith('.png') || file.endsWith('.svg') || file.endsWith('.html')) && (
                       <a href={getFileUrl(file)} download={file} className={styles.vizDownloadButton} title={`Download ${file}`}>
                         <FontAwesomeIcon icon={faDownload} />
                       </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
           ) : (
             <section className={styles.card}>
                  <h2>Visualizations</h2>
                  <p className={styles.noDataText}>No visualization files were found for this run.</p>
             </section>
           )}
        </div>

        {/* --- Right Column --- */}
        <div className={styles.rightColumn}>
          {/* --- Summary Section --- */}
          {summary && Object.keys(summary).length > 0 ? (
            <section className={`${styles.card} ${styles.sidebarCard}`}>
              <h2>Run Summary</h2>
              <ul className={styles.summaryList}>
                {/* Display key insights if available */}
                {summary.key_insights?.map((insight, index) => (
                  <li key={`insight-${index}`}>
                    <FontAwesomeIcon icon={faBrain} /> <span>{insight}</span>
                  </li>
                ))}
                 {/* Divider */}
                 {(summary.key_insights?.length > 0) && <li className={styles.summaryDivider}></li>}

                 {/* Display structured summary fields */}
                 <li><span>Model Type:</span> <span>{summary.model_type || 'N/A'}</span></li>
                 <li><span>Task Type:</span> <span>{summary.task || 'N/A'}</span></li>
                 <li><span>Training Iterations:</span> <span>{summary.training_iters || 'N/A'}</span></li>
                 <li><span>Training Time:</span> <span>{formatTime(summary.training_time_seconds)}</span></li>
                 {/* Add more fields from summary if needed */}
              </ul>
            </section>
           ) : (
              <section className={`${styles.card} ${styles.sidebarCard}`}>
                   <h2>Run Summary</h2>
                   <p className={styles.noDataText}>No summary data available.</p>
              </section>
           )}

          {/* --- Downloads Section --- */}
          {downloadableFiles.length > 0 ? (
            <section className={`${styles.card} ${styles.sidebarCard}`}>
              <h2>Download Artifacts</h2>
              <div className={styles.downloadList}>
                {downloadableFiles.map((file) => (
                  <a key={file} href={getFileUrl(file)} download={file} className={styles.downloadLink}>
                    <span className={styles.downloadFileInfo}>
                      <FontAwesomeIcon icon={faFileAlt} /> {file}
                    </span>
                    <FontAwesomeIcon icon={faDownload} className={styles.downloadIcon} />
                  </a>
                ))}
              </div>
            </section>
           ) : (
              <section className={`${styles.card} ${styles.sidebarCard}`}>
                   <h2>Download Artifacts</h2>
                   <p className={styles.noDataText}>No downloadable files found.</p>
              </section>
           )}

           {/* --- Actions Section (Keep as is) --- */}
           <section className={`${styles.card} ${styles.sidebarCard}`}>
              <h2>Actions</h2>
               <Link to="/dashboard" className={styles.actionButton}>
                 <FontAwesomeIcon icon={faArrowLeft} /> <span>Back to Dashboard</span>
               </Link>
               {/* Add other actions like 'Deploy' or 'Retrain' here */}
          </section>
        </div>
      </div>
    </motion.div>
  );
};

export default Results;