// frontend/src/pages/CleanData.jsx
import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSpinner, faCheckCircle, faExclamationTriangle, faMagic, faArrowRight } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';

import StepIndicator from '../components/StepIndicator';
import socket, { connectSocket, disconnectSocket, joinTrainingRoom, leaveTrainingRoom } from '../lib/socket';
import api from '../lib/api';
import styles from './CleanData.module.css';
import Spinner from '../components/Spinner';

// Initial Cleaning Options
const initialOptions = {
    remove_duplicates: true,
    handle_missing: false,
    missing_method: 'remove', // 'remove', 'mean', 'median', 'mode'
    handle_outliers: false,
    outlier_method: 'iqr', // 'iqr', maybe others later
    encode_categorical: true,
    feature_scaling: false,
    scaling_method: 'standard', // 'standard', 'minmax', 'robust'
};

const CleanData = () => {
    const { runId } = useParams();
    const navigate = useNavigate();
    const [logs, setLogs] = useState([]);
    const [status, setStatus] = useState('LOADING_DETAILS');
    const [options, setOptions] = useState(initialOptions);
    const [runDetails, setRunDetails] = useState(null);
    const [isLoadingDetails, setIsLoadingDetails] = useState(true);
    const [cleaningReport, setCleaningReport] = useState(null);
    const [cleanedPreview, setCleanedPreview] = useState(null); // Preview AFTER cleaning

    const logsEndRef = useRef(null);
    const cleaningStartedRef = useRef(false); // Ref to prevent double-clicks
    const toastShownRef = useRef({ success: false, error: false });
    const isMountedRef = useRef(true); // Ref to track component mount status

    // --- Fetch initial run details (includes original analysis results) ---
    useEffect(() => {
        isMountedRef.current = true;
        setIsLoadingDetails(true);
        api.get(`/training/run/${runId}`)
            .then(res => {
                if (!isMountedRef.current) return;
                const details = res.data;
                setRunDetails(details);
                const fetchedStatus = details.status || 'UNKNOWN';

                // Decide initial UI status based on fetched status
                if (['SUCCESS', 'CLEANING_FAILED', 'CLEANING_SUCCESS', 'CLEANING'].includes(fetchedStatus)) {
                    setStatus(fetchedStatus === 'SUCCESS' ? 'READY' : fetchedStatus);
                    if (details.cleaning_report) {
                        setCleaningReport(details.cleaning_report);
                        if (details.cleaning_report.preview_cleaned_data) {
                             setCleanedPreview(details.cleaning_report.preview_cleaned_data);
                        }
                    }
                } else {
                    toast.error("Analysis must be successful before cleaning.", { duration: 4000 });
                    navigate(`/run/${runId}/analyze`);
                }
            })
            .catch(err => {
                if (!isMountedRef.current) return;
                toast.error("Failed to load run details.");
                setStatus('FAILED');
            })
            .finally(() => {
                if (isMountedRef.current) setIsLoadingDetails(false);
            });
        
        // Main unmount cleanup
        return () => {
            isMountedRef.current = false;
            console.log("CleanData: Unmounting, leaving room and disconnecting socket.");
            leaveTrainingRoom(runId);
            disconnectSocket(); // Disconnect fully on unmount
        };
    }, [runId, navigate]);

     // WebSocket Effect
     useEffect(() => {
        const shouldConnect = ['READY', 'CLEANING', 'CLEANING_FAILED', 'CONNECTING'].includes(status);
        if (isLoadingDetails || !runDetails || !shouldConnect) {
             return;
        }

        connectSocket();
        const onConnect = () => {
            if (!isMountedRef.current) return;
             console.log('Socket connected for cleaning, joining room...');
             joinTrainingRoom(runId);
             setStatus(prev => prev === 'CONNECTING' ? (runDetails?.status === 'SUCCESS' ? 'READY' : runDetails?.status) : prev);
        };
        const onLog = (log) => {
            if (!isMountedRef.current) return;
            if (!log.timestamp) log.timestamp = new Date().toISOString();
            setLogs(prev => [...prev, log]);
             if (log.type === 'cleaning_report' && log.data) {
                setCleaningReport(log.data);
                if (log.data.preview_cleaned_data) {
                     setCleanedPreview(log.data.preview_cleaned_data);
                }
             } else if (log.type === 'analysis_result' && log.key === 'preview_cleaned_data' && log.data) {
                 setCleanedPreview(log.data);
             }
        };
        const onStatusUpdate = (update) => {
            if (!isMountedRef.current) return;
            const newStatus = update.status;
            console.log("Received status update:", newStatus);
            if (['CLEANING', 'CLEANING_SUCCESS', 'CLEANING_FAILED', 'FAILED'].includes(newStatus)) {
                setStatus(currentStatus => {
                    if (['CLEANING_SUCCESS', 'CLEANING_FAILED', 'FAILED'].includes(currentStatus)) {
                        return currentStatus;
                    }
                    if (newStatus === 'CLEANING_FAILED') {
                        cleaningStartedRef.current = false; // Allow retry
                    }
                    return newStatus;
                });
            } else {
                console.log("Ignoring status update irrelevant to cleaning:", newStatus);
            }
        };

        const handleDisconnect = (reason) => {
            if (!isMountedRef.current) return;
            console.log('CleanData: Socket disconnected:', reason);
            if (status === 'CLEANING') setStatus('CONNECTING');
        };
        const handleError = (err) => {
            if (!isMountedRef.current) return;
            console.error('CleanData: Socket error:', err);
            toast.error(`Socket error: ${err.msg || 'Connection failed'}`);
        };

        socket.on('connect', onConnect);
        socket.on('training_log', onLog);
        socket.on('status_update', onStatusUpdate);
        socket.on('error', handleError);
        socket.on('disconnect', handleDisconnect);

        // --- START FIX [Issue #12] ---
        // Cleanup: Only leave the room.
        return () => {
            console.log("CleanData: Cleaning up WebSocket listeners and leaving room.");
            if (socket.connected) {
                leaveTrainingRoom(runId);
            }
            socket.off('connect', onConnect);
            socket.off('training_log', onLog);
            socket.off('status_update', onStatusUpdate);
            socket.off('error');
            socket.off('disconnect');
        };
        // --- END FIX ---
    }, [runId, isLoadingDetails, runDetails, status]);

    // Toast Effect
     useEffect(() => {
        if (status === 'CLEANING_SUCCESS' && !toastShownRef.current.success) {
            toast.success('Data Cleaning Complete!');
            toastShownRef.current.success = true;
        } else if (status === 'CLEANING_FAILED' && !toastShownRef.current.error) {
            toast.error('Data Cleaning Failed. Check logs.');
            toastShownRef.current.error = true;
        }
    }, [status]);

    // Scroll logs Effect
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    // Handle form changes
    const handleOptionChange = (e) => {
        const { name, value, type, checked } = e.target;
        setOptions(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }));
    };

    // Trigger cleaning task
    const handleStartCleaning = () => {
        if (status !== 'READY' && status !== 'CLEANING_FAILED') return;
        cleaningStartedRef.current = true;
        
        // --- START FIX [ReferenceError] ---
        setCleaningReport(null); // Clear previous report STATE
        // --- END FIX ---

        setCleanedPreview(null);
        setLogs([{ type: 'CLIENT', message: 'Resetting state for new cleaning run...', timestamp: new Date().toISOString() }]);
        toastShownRef.current = { success: false, error: false };

        setStatus('CLEANING');
        toast.loading('Starting data cleaning...');
        setLogs(prev => [...prev, { type: 'CLIENT', message: 'Cleaning task requested...', timestamp: new Date().toISOString() }]);

        const optionsToSend = { ...options };
        if (!options.handle_missing) delete optionsToSend.missing_method;
        if (!options.handle_outliers) delete optionsToSend.outlier_method;
        if (!options.feature_scaling) delete optionsToSend.scaling_method;

        api.post(`/training/run/${runId}/clean`, optionsToSend)
            .then(() => toast.dismiss())
            .catch(err => {
                toast.dismiss();
                const errorMsg = err.response?.data?.msg || 'Failed to start cleaning task.';
                toast.error(errorMsg);
                setStatus('CLEANING_FAILED');
            });
    };

    // --- RENDER FUNCTIONS ---

    // Generic Log Line Renderer
    const LogLine = ({ log }) => {
        let lineStyle = styles.logLineInfo;
        if (log.type === 'ERROR' || log.log_type === 'ERROR') lineStyle = styles.logLineError;
        else if (log.log_type === 'WARNING') lineStyle = styles.logLineWarning;
        else if (log.log_type === 'SUCCESS') lineStyle = styles.logLineSuccess;
        else if (log.type === 'cleaning_report' || log.type === 'analysis_result') lineStyle = styles.logLineMetric;
        else if (log.type === 'CLIENT') lineStyle = styles.logLineClient;
        
        let messageContent = log.message || '';
         if (log.type === 'cleaning_report') {
             messageContent = `[Report] Cleaning operations summary received.`;
         } else if (log.type === 'analysis_result') {
              messageContent = `[Data] Received ${log.key || 'data'}`;
         }

        return (
            <div className={lineStyle}>
                <span className={styles.logTimestamp}>[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                <span className={styles.logMessage}>{messageContent}</span>
            </div>
        );
     };

    // Status Display Renderer
    const getStatusDisplay = () => {
        switch(status) {
          case 'CLEANING': return <span className={styles.statusTraining}><FontAwesomeIcon icon={faSpinner} spin className={styles.statusIcon} />Cleaning Data...</span>;
          case 'CLEANING_SUCCESS': return <span className={styles.statusSuccess}><FontAwesomeIcon icon={faCheckCircle} className={styles.statusIcon} />Cleaning Complete</span>;
          case 'CLEANING_FAILED': return <span className={styles.statusFailed}><FontAwesomeIcon icon={faExclamationTriangle} className={styles.statusIcon} />Cleaning Failed</span>;
          case 'READY': return <span className={styles.statusPending}><FontAwesomeIcon icon={faCheckCircle} className={styles.statusIcon} />Ready to Clean</span>;
          case 'LOADING_DETAILS': return <span className={styles.statusPending}><FontAwesomeIcon icon={faSpinner} spin className={styles.statusIcon} />Loading...</span>;
          case 'FAILED': return <span className={styles.statusFailed}><FontAwesomeIcon icon={faExclamationTriangle} className={styles.statusIcon} />Error Loading</span>;
          case 'CONNECTING':
          default: return <span className={styles.statusPending}><FontAwesomeIcon icon={faSpinner} spin className={styles.statusIcon} />Connecting...</span>;
        }
    };

    // Generic Preview Table Renderer
    const RenderPreviewTable = ({ previewData, title }) => {
        if (!previewData) {
            return <p className={styles.waitingText}>{title} will appear here.</p>;
        }
        const { headers, rows, problem_cells = {} } = previewData;
        if (!headers || !rows || !Array.isArray(headers) || !Array.isArray(rows)) {
            console.error("Invalid preview data structure:", previewData);
            return <p className={styles.errorText}>Preview data format invalid.</p>;
        }

        return (
            <div className={styles.previewSection}>
                <h4>{title}</h4>
                <div className={styles.tablePreviewContainer}>
                    <table>
                        <thead>
                            <tr>{headers.map((h, i) => <th key={i}>{h}</th>)}</tr>
                        </thead>
                        <tbody>
                            {rows.map((row, rIdx) => (
                                <tr key={rIdx}>
                                    {row.map((cell, cIdx) => {
                                        const isProblem = problem_cells[rIdx]?.includes(cIdx);
                                        const isNull = cell === null;
                                        let cellClass = '';
                                        if (isProblem) cellClass = styles.problemCell;
                                        else if (isNull) cellClass = styles.nullValueCell;

                                        return (
                                            <td key={cIdx} className={cellClass}>
                                                {isNull ? <span className={styles.nullValue}>NULL</span> : String(cell)}
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                 {Object.keys(problem_cells).length > 0 && title.toLowerCase().includes("original") && (
                     <p className={styles.previewNote}>Highlighted cells indicate potential issues (e.g., missing values).</p>
                 )}
                  {Object.keys(problem_cells).length > 0 && title.toLowerCase().includes("cleaned") && (
                     <p className={styles.previewNote}>Highlighted cells indicate issues remaining AFTER cleaning.</p>
                 )}
            </div>
        );
    };

    // --- Component Render ---

    if (isLoadingDetails) return <Spinner fullPage={true} />;
    if (status === 'FAILED' && !runDetails) {
         return (
             <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                 <StepIndicator currentStep="Analyze & Clean" />
                 <div className={styles.errorContainer}> {/* Assumes .errorContainer style exists */
                     <FontAwesomeIcon icon={faExclamationTriangle} size="3x"/>
                    }<p>Error loading run details. Cannot proceed.</p>
                   </div>
             </motion.div>
         );
    }

    const showCleaningOptions = runDetails && (runDetails.model_id_str.includes('random_forest') || runDetails.model_id_str.includes('xgboost'));
    const canInteractWithForm = runDetails && ['READY', 'CLEANING_FAILED'].includes(status);
    const originalPreviewData = runDetails?.analysis_results?.preview_data;


    return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <StepIndicator currentStep="Analyze & Clean" />
            <div className={styles.header}>
                <h1>Data Cleaning</h1>
                 <div className={styles.statusDisplay}>{getStatusDisplay()}</div>
            </div>

            <div className={styles.mainGrid}>
                {/* --- Left Column: Options & Actions --- */}
                <div className={styles.leftColumn}>
                    {/* Only show options card if applicable and details loaded */}
                    {runDetails && showCleaningOptions && (
                         <section className={styles.card}>
                             <h2>Cleaning Options</h2>
                             {!(status === 'READY' || status === 'CLEANING_FAILED' || status === 'CLEANING' || status === 'CLEANING_SUCCESS') && (
                                  <p className={styles.waitingText}>Loading configuration...</p>
                             )}
                             {(status === 'READY' || status === 'CLEANING_FAILED' || status === 'CLEANING' || status === 'CLEANING_SUCCESS') && (
                                  <form className={styles.optionsForm}>
                                      <fieldset disabled={status === 'CLEANING' || status === 'CLEANING_SUCCESS'}>
                                          {/* Handle Missing */}
                                          <div className={styles.optionGroup}>
                                              <label className={styles.optionToggle}>
                                                  <input type="checkbox" name="handle_missing" checked={options.handle_missing} onChange={handleOptionChange} />
                                                  <span>Handle Missing Values</span>
                                              </label>
                                              {options.handle_missing && (
                                                  <select name="missing_method" value={options.missing_method} onChange={handleOptionChange} className={styles.optionSelect}>
                                                      <option value="remove">Remove Rows</option>
                                                      <option value="mean">Fill with Mean (Numeric)</option>
                                                      <option value="median">Fill with Median (Numeric)</option>
                                                      <option value="mode">Fill with Mode (Most Frequent)</option>
                                                      <option value="knn">Fill with KNN (Numeric)</option>
                                                  </select>
                                              )}
                                          </div>
                                          {/* Handle Duplicates */}
                                          <div className={styles.optionGroup}>
                                               <label className={styles.optionToggle}>
                                                   <input type="checkbox" name="remove_duplicates" checked={options.remove_duplicates} onChange={handleOptionChange}/>
                                                   <span>Remove Duplicate Rows</span>
                                               </label>
                                           </div>
                                          {/* Handle Outliers */}
                                          <div className={styles.optionGroup}>
                                               <label className={styles.optionToggle}>
                                                   <input type="checkbox" name="handle_outliers" checked={options.handle_outliers} onChange={handleOptionChange}/>
                                                   <span>Handle Outliers (IQR Capping)</span>
                                               </label>
                                           </div>
                                          {/* Encode Categorical */}
                                          <div className={styles.optionGroup}>
                                               <label className={styles.optionToggle}>
                                                   <input type="checkbox" name="encode_categorical" checked={options.encode_categorical} onChange={handleOptionChange}/>
                                                   <span>Encode Categorical (LabelEncode)</span>
                                               </label>
                                           </div>
                                          {/* Feature Scaling */}
                                          <div className={styles.optionGroup}>
                                              <label className={styles.optionToggle}>
                                                  <input type="checkbox" name="feature_scaling" checked={options.feature_scaling} onChange={handleOptionChange} />
                                                  <span>Apply Feature Scaling</span>
                                              </label>
                                              {options.feature_scaling && (
                                                  <select name="scaling_method" value={options.scaling_method} onChange={handleOptionChange} className={styles.optionSelect}>
                                                      <option value="standard">Standard Scaler</option>
                                                      <option value="minmax">MinMax Scaler</option>
                                                      <option value="robust">Robust Scaler</option>
                                                  </select>
                                              )}
                                           </div>
                                      </fieldset>
                                  </form>
                             )}
                         </section>
                     )}
                     {runDetails && !showCleaningOptions && (
                          <section className={styles.card}>
                             <h2>Cleaning Options</h2>
                              <p className={styles.infoText}>No specific cleaning options available for this model type. Click "Apply Cleaning" to copy the data, or "Skip" to configure training directly.</p>
                          </section>
                     )}

                    {/* Actions Card */}
                    <section className={`${styles.card} ${styles.actionsCard}`}>
                         <h2>Actions</h2>
                          <button
                            onClick={handleStartCleaning}
                            disabled={!canInteractWithForm || status === 'CLEANING'}
                            className={styles.primaryButton}
                        >
                            <FontAwesomeIcon icon={status === 'CLEANING' ? faSpinner : faMagic} spin={status === 'CLEANING'}/>
                            <span>{status === 'CLEANING' ? 'Cleaning...' : (status === 'CLEANING_FAILED' ? 'Retry Cleaning' : 'Apply Cleaning')}</span>
                        </button>
                         <button
                            onClick={() => navigate(`/run/${runId}/configure`)}
                            disabled={status !== 'CLEANING_SUCCESS'}
                            className={styles.secondaryButton}
                        >
                            <span>Proceed to Configuration</span>
                             <FontAwesomeIcon icon={faArrowRight} />
                        </button>
                        <button
                           onClick={() => navigate(`/run/${runId}/configure`)}
                           disabled={!(runDetails?.status === 'SUCCESS' || status === 'CLEANING_SUCCESS' || status === 'CLEANING_FAILED')}
                           className={styles.skipButton}
                           title="Proceed to training configuration without applying cleaning steps."
                        >
                           Skip Cleaning
                        </button>
                    </section>
                </div>

                {/* --- Right Column: Logs, Report, Previews --- */}
                 <section className={`${styles.card} ${styles.logsCardContainer}`}>
                     <h2>Cleaning Log & Results</h2>
                      {/* --- Original Preview --- */}
                      <RenderPreviewTable previewData={originalPreviewData} title="Original Data Preview (Issues Highlighted)" />

                      {/* Display Report Summary (if available) */}
                      {cleaningReport && (
                          <div className={styles.reportSummary}>
                              <h4>Cleaning Summary</h4>
                               <p><strong>Action:</strong> {cleaningReport.summary?.action_taken || (showCleaningOptions ? 'Applied selected options' : 'N/A')}</p>
                              <p><strong>Time:</strong> {cleaningReport.summary?.cleaning_time_seconds?.toFixed(1) ?? 'N/A'}s</p>
                               {showCleaningOptions && (
                                   <>
                                       <p><strong>Duplicates Removed:</strong> {cleaningReport.operations_performed?.duplicates_removed ?? 0}</p>
                                       <p><strong>Missing Fixed:</strong> {cleaningReport.operations_performed?.missing_values_fixed ?? 0} {options.handle_missing ? `(using ${options.missing_method})` : ''}</p>
                                       <p><strong>Outliers Handled:</strong> {cleaningReport.operations_performed?.outliers_handled ?? 0}</p>
                                       <p><strong>Categorical Encoded:</strong> {cleaningReport.operations_performed?.categorical_encoded ?? 0}</p>
                                       <p><strong>Features Scaled:</strong> {cleaningReport.operations_performed?.feature_scaling && cleaningReport.operations_performed.feature_scaling !== 'None' ? `Yes (using ${cleaningReport.operations_performed.feature_scaling})` : 'No'}</p>
                                       <p><strong>Rows Removed:</strong> {cleaningReport.summary?.rows_removed ?? 0} ({cleaningReport.summary?.data_loss_percentage ?? 0}%)</p>
                                   </>
                               )}
                              {cleaningReport.summary?.error && (
                                  <p className={styles.reportIssue}><strong>Error:</strong> {cleaningReport.summary.error}</p>
                              )}
                          </div>
                      )}

                      {/* Display Cleaned Preview (conditionally) */}
                      {(status === 'CLEANING' || status === 'CLEANING_SUCCESS' || status === 'CLEANING_FAILED') && (
                           <RenderPreviewTable previewData={cleanedPreview} title="Cleaned Data Preview" />
                      )}

                      {/* Display Logs */}
                      <div style={{marginTop: '1rem'}}>
                          <h4>Live Log</h4>
                          <div className={styles.logsContainer}>
                             {logs.map((log, index) => <LogLine key={`${log.timestamp}-${index}`} log={log} />)}
                             <div ref={logsEndRef} />
                         </div>
                      </div>
                 </section>
            </div>
        </motion.div>
    );
};

export default CleanData;