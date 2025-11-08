// frontend/src/pages/AnalyzeData.jsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSpinner, faCheckCircle, faExclamationTriangle, faFileAlt, faChartBar, faArrowRight } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';

import StepIndicator from '../components/StepIndicator';
import socket, { connectSocket, disconnectSocket, joinTrainingRoom, leaveTrainingRoom } from '../lib/socket';
import api from '../lib/api';
import styles from './AnalyzeData.module.css';
import Spinner from '../components/Spinner';

const AnalyzeData = () => {
    const { runId } = useParams();
    const navigate = useNavigate();
    const [logs, setLogs] = useState([]);
    const [analysisResults, setAnalysisResults] = useState(null); // State to hold the full analysis object
    const [runDetails, setRunDetails] = useState(null);
    const [runStatus, setRunStatus] = useState('LOADING_DETAILS');
    const [isFetchingDetails, setIsFetchingDetails] = useState(true);
    const [fetchError, setFetchError] = useState(null);

    const logsEndRef = useRef(null);
    const analysisTriggeredRef = useRef(false);
    const toastShownRef = useRef({ success: false, error: false });
    const isMountedRef = useRef(true); // Ref to track component mount status

    // --- Fetch Initial Run Details & Trigger Task ---
    useEffect(() => {
        isMountedRef.current = true;
        setIsFetchingDetails(true);
        setFetchError(null);
        toastShownRef.current = { success: false, error: false };

        api.get(`/training/run/${runId}`)
            .then(res => {
                if (!isMountedRef.current) return;
                const details = res.data;
                setRunDetails(details);
                const fetchedStatus = details.status || 'UNKNOWN';

                if (details.analysis_results) {
                    setAnalysisResults(details.analysis_results);
                }

                const isTerminal = ['SUCCESS', 'FAILED', 'ANALYSIS_FAILED', 'CLEANING_SUCCESS', 'CLEANING_FAILED'].includes(fetchedStatus);
                const isRunning = ['ANALYZING', 'CLEANING', 'TRAINING'].includes(fetchedStatus);

                if (isTerminal || isRunning) {
                    setRunStatus(fetchedStatus);
                } else {
                    // Task needs to be triggered. Do it now to avoid race conditions.
                    setRunStatus('STARTING'); // Give immediate feedback
                    setLogs(prev => [...prev, { type: 'CLIENT', message: 'Requesting analysis task start...', timestamp: new Date().toISOString() }]);

                    api.post(`/training/run/${runId}/analyze`)
                        .catch(err => {
                            if (!isMountedRef.current) return;
                            const errorMsg = err.response?.data?.msg || 'Failed to start analysis task.';
                            toast.error(errorMsg);
                            setRunStatus('FAILED');
                            setLogs(prev => [...prev, { type: 'ERROR', message: `API Error: ${errorMsg}`, timestamp: new Date().toISOString() }]);
                        });
                }
            })
            .catch(err => {
                if (!isMountedRef.current) return;
                const errorMsg = err.response?.data?.msg || "Could not load run details.";
                setFetchError(errorMsg);
                setRunStatus('FETCH_FAILED');
            })
            .finally(() => {
                if (isMountedRef.current) setIsFetchingDetails(false);
            });

        // Main cleanup for when the component fully unmounts
        return () => {
            isMountedRef.current = false;
            leaveTrainingRoom(runId);
            disconnectSocket(); // Disconnect fully on unmount
        };
    }, [runId]);

    // --- WebSocket Connection and Event Handling ---
    useEffect(() => {
        // Connect to WebSocket if details are loaded and the task is in a non-terminal state.
        const isTerminal = ['SUCCESS', 'FAILED', 'ANALYSIS_FAILED', 'CLEANING_SUCCESS', 'CLEANING_FAILED', 'FETCH_FAILED'].includes(runStatus);
        const shouldConnect = !isFetchingDetails && !fetchError && !isTerminal;

        if (!shouldConnect) {
            return;
        }

        connectSocket();

        const handleConnect = () => {
            if (!isMountedRef.current) return;
            joinTrainingRoom(runId);
        };

        const handleLog = (log) => {
            if (!isMountedRef.current) return;
            if (!log.timestamp) log.timestamp = new Date().toISOString();
            setLogs(prev => [...prev, log]);

            if (log.type === 'analysis_result' && log.data) {
                setAnalysisResults(log.data);
            }
        };

        const handleStatusUpdate = (update) => {
            if (!isMountedRef.current) return;
            const newStatus = update.status;
            setRunStatus(prevStatus => {
                if (['SUCCESS', 'FAILED', 'ANALYSIS_FAILED'].includes(prevStatus) && !['SUCCESS', 'FAILED', 'ANALYSIS_FAILED'].includes(newStatus)) {
                    return prevStatus;
                }
                return newStatus;
            });
        };

        const handleDisconnect = (reason) => {
            if (!isMountedRef.current) return;
            if (!['SUCCESS', 'FAILED'].includes(runStatus)) {
                setRunStatus('CONNECTING'); // Show reconnecting state
            }
        };

        const handleError = (err) => {
            if (!isMountedRef.current) return;
            toast.error(`Socket error: ${err.msg || 'Connection failed'}`);
        };

        // Register listeners
        socket.on('connect', handleConnect);
        socket.on('disconnect', handleDisconnect);
        socket.on('error', handleError);
        socket.on('training_log', handleLog);
        socket.on('status_update', handleStatusUpdate);

        // Cleanup listeners on effect cleanup
        return () => {
            if (socket.connected) {
                leaveTrainingRoom(runId);
            }
            socket.off('connect', handleConnect);
            socket.off('disconnect', handleDisconnect);
            socket.off('error', handleError);
            socket.off('training_log', handleLog);
            socket.off('status_update', handleStatusUpdate);
        };
    }, [runId, isFetchingDetails, fetchError, runStatus]);


    // --- (Keep toast and scroll effects as before) ---
     useEffect(() => {
        if (status === 'SUCCESS' && !toastShownRef.current.success) {
            toast.success('Analysis Complete!');
            toastShownRef.current.success = true;
        } else if ((status === 'FAILED' || status === 'ANALYSIS_FAILED') && !toastShownRef.current.error) {
            toast.error('Analysis Failed. Check logs.');
            toastShownRef.current.error = true;
        }
     }, [runStatus]);

     useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
     }, [logs]);


    // --- LogLine Component ---
    const LogLine = ({ log }) => {
        let lineStyle = styles.logLineInfo;
        let messageContent = log.message || '';
        const timestamp = log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '';
        let prefix = ''; // Prefix like [stderr]

        // Check for specific log_type from script
        if (log.log_type === 'ERROR') lineStyle = styles.logLineError;
        else if (log.log_type === 'WARNING') lineStyle = styles.logLineWarning;
        else if (log.log_type === 'SUCCESS') lineStyle = styles.logLineSuccess;
        
        // Handle structured log types
        switch(log.type) {
            case 'ERROR': // Error from Celery task itself
                lineStyle = styles.logLineError;
                break;
            case 'analysis_result':
                lineStyle = styles.logLineMetric; // Use metric/special style
                messageContent = `[Data Structure] Received ${log.key || 'full results'}`;
                break;
            case 'cleaning_report':
                 lineStyle = styles.logLineMetric;
                 messageContent = `[Data Structure] Received Cleaning Report`;
                 break;
            case 'CLIENT': // Log from this component
                lineStyle = styles.logLineClient;
                break;
            default: // Default 'log' or unknown
                 // Check message content for script prefixes
                 const match = messageContent.match(/^\[(script|stderr)\]\s*/);
                 if (match) {
                      prefix = match[0];
                      messageContent = messageContent.substring(match[0].length);
                      if (match[1] === 'stderr') lineStyle = styles.logLineError;
                 }
                 break;
        }

        return (
            <div className={lineStyle}>
                <span className={styles.logTimestamp}>[{timestamp}]</span>
                <span className={styles.logPrefix}>{prefix}</span>
                <span className={styles.logMessage}>{messageContent}</span>
            </div>
        );
     };

    // --- Status Display Function ---
    const getStatusDisplay = () => {
        switch(runStatus) {
            case 'ANALYZING': return <span className={styles.statusTraining}><FontAwesomeIcon icon={faSpinner} spin className={styles.statusIcon} />Analyzing Data...</span>;
            case 'STARTING': return <span className={styles.statusTraining}><FontAwesomeIcon icon={faSpinner} spin className={styles.statusIcon} />Starting Task...</span>;
            case 'PENDING_TRIGGER': return <span className={styles.statusPending}><FontAwesomeIcon icon={faSpinner} spin className={styles.statusIcon} />Waiting to Start...</span>;
            case 'SUCCESS': return <span className={styles.statusSuccess}><FontAwesomeIcon icon={faCheckCircle} className={styles.statusIcon} />Analysis Complete</span>;
            case 'FAILED':
            case 'ANALYSIS_FAILED':
            case 'FETCH_FAILED':
                 return <span className={styles.statusFailed}><FontAwesomeIcon icon={faExclamationTriangle} className={styles.statusIcon} />Analysis Failed</span>;
            // Handle states where user lands here but task is further along
            case 'CLEANING':
            case 'CLEANING_SUCCESS':
            case 'TRAINING':
                 return <span className={styles.statusSuccess}><FontAwesomeIcon icon={faCheckCircle} className={styles.statusIcon} />Analysis Complete</span>;
            case 'JOINING_ROOM':
            case 'CONNECTING':
            case 'LOADING_DETAILS':
            default: return <span className={styles.statusPending}><FontAwesomeIcon icon={faSpinner} spin className={styles.statusIcon} />Initializing...</span>;
        }
    };

    // --- RenderSummary Component ---
    const RenderSummary = () => {
        if (!analysisResults && ['CONNECTING', 'PENDING_TRIGGER', 'JOINING_ROOM', 'STARTING', 'ANALYZING', 'LOADING_DETAILS'].includes(runStatus)) {
           return <p className={styles.waitingText}>Waiting for analysis results...</p>;
        }
        if (['FAILED', 'ANALYSIS_FAILED', 'FETCH_FAILED'].includes(runStatus)) {
           return <p className={styles.errorText}>Analysis failed. Check logs for details.</p>;
        }
        if (!analysisResults || Object.keys(analysisResults).length === 0) {
           // This handles page refresh for SUCCESS state before WS connects
           if (runStatus === 'SUCCESS' && runDetails?.analysis_results) {
               setAnalysisResults(runDetails.analysis_results); // Load from fetched details
               return <p className={styles.waitingText}>Loading summary...</p>;
           }
           return <p className={styles.waitingText}>No summary data received yet.</p>;
        }

        const modelType = runDetails?.model_id_str || '';
        const isTabular = modelType.includes('random_forest') || modelType.includes('xgboost');
        const isImageZip = modelType.includes('cnn');

        const basicInfo = analysisResults.basic_info || {};
        const dataQuality = analysisResults.data_quality || {};
        const classSummary = analysisResults.class_summary || {}; // For image_cnn
        const issues = analysisResults.issues || [];
        const missingValues = dataQuality.missing_values || {};
        const missingCount = Object.values(missingValues).reduce((s, c) => s + c, 0);
        const duplicateRows = dataQuality.duplicate_rows ?? 0;
        const errorIssues = issues.filter(i => i.severity === 'ERROR' || i.severity === 'CRITICAL').length;

        return (
            <ul className={styles.summaryList}>
                {/* Basic Info */}
                {isTabular && basicInfo.shape ? (
                    <>
                        <li><span>Total Rows:</span> <span>{basicInfo.shape[0] ?? 'N/A'}</span></li>
                        <li><span>Total Columns:</span> <span>{basicInfo.shape[1] ?? 'N/A'}</span></li>
                    </>
                ) : isImageZip ? (
                    <>
                        <li><span>Files Extracted:</span> <span>{basicInfo.total_files_extracted ?? 'N/A'}</span></li>
                        <li><span>Detected Splits:</span> <span>{(basicInfo.detected_splits || []).join(', ') || 'None'}</span></li>
                    </>
                ) : (
                     <li><span>Shape:</span> <span>{(basicInfo.shape || []).join(' x ') || 'N/A'}</span></li>
                )}
                
                {/* Data Quality */}
                {isTabular ? (
                    <>
                        <li className={missingCount > 0 ? styles.summaryIssue : ''}>
                             <span>Missing Values:</span>
                             <span>{missingCount}</span>
                         </li>
                         <li className={duplicateRows > 0 ? styles.summaryIssue : ''}>
                             <span>Duplicate Rows:</span>
                             <span>{duplicateRows}</span>
                         </li>
                    </>
                ) : null}
                
                {/* Class Summary */}
                {isImageZip && (
                    <li className={(classSummary.count ?? 2) < 2 ? styles.summaryIssue : ''}>
                        <span>Detected Classes:</span>
                        <span>{classSummary.count ?? 'N/A'}</span>
                    </li>
                )}

                {/* Issues */}
                <li className={issues.length > 0 ? styles.summaryIssue : ''}>
                    <span>Issues Found:</span>
                    <span>{issues.length} {errorIssues > 0 ? `(${errorIssues} errors)` : ''}</span>
                </li>
            </ul>
        );
    };

    // --- RenderPreview Component ---
    const RenderPreview = () => {
        const preview = analysisResults?.preview_data;

        if (!preview && ['CONNECTING', 'PENDING_TRIGGER', 'JOINING_ROOM', 'STARTING', 'ANALYZING', 'LOADING_DETAILS'].includes(runStatus)) {
             return <p className={styles.waitingText}>Preview data not available yet.</p>;
        }
         if (['FAILED', 'ANALYSIS_FAILED', 'FETCH_FAILED'].includes(runStatus)) {
            return <p className={styles.errorText}>Preview unavailable due to analysis failure.</p>;
         }
        if (!preview || (!preview.rows && !preview.file_list_head)) {
             if (runStatus === 'SUCCESS' && runDetails?.analysis_results?.preview_data) {
                 setAnalysisResults(runDetails.analysis_results); // Load from fetched details
                 return <p className={styles.waitingText}>Loading preview...</p>;
             }
             return <p className={styles.waitingText}>No preview data received yet.</p>;
        }

        const modelType = runDetails?.model_id_str || '';
        const isTabular = modelType.includes('random_forest') || modelType.includes('xgboost');
        const isImageZip = modelType.includes('cnn');

        if (isTabular && preview.headers && preview.rows) {
            const { headers = [], rows = [], problem_cells = {} } = preview;
            const displayRows = rows.slice(0, 20); // Show max 20 rows
            return (
                <div className={styles.tablePreviewContainer}>
                    <table>
                        <thead>
                            <tr>{headers.map((h, i) => <th key={i}>{h}</th>)}</tr>
                        </thead>
                        <tbody>
                            {displayRows.map((row, rIdx) => (
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
                     {rows.length > displayRows.length && <p className={styles.previewTruncated}>Preview limited to first {displayRows.length} rows.</p>}
                </div>
            );
        } else if (isImageZip && preview.file_list_head) {
             const { file_list_head = [] } = preview;
             return (
                 <ul className={styles.fileListPreview}>
                     {file_list_head.slice(0, 20).map((file, i) => <li key={i}>{file}</li>)}
                     {file_list_head.length === 0 && <li>No files found in preview.</li>}
                      {file_list_head.length > 20 && <li>... (preview limited)</li>}
                 </ul>
             );
        }
        return <p>Preview format not supported for this model type.</p>;
    };

    // --- Loading / Error States ---
    if (isFetchingDetails) return <Spinner fullPage={true} />;
    if (fetchError && !runDetails) {
         return (
             <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                 <StepIndicator currentStep="Analyze & Clean" />
                 <div className={styles.errorContainer}>
                     <FontAwesomeIcon icon={faExclamationTriangle} size="3x"/>
                     <p>{fetchError}</p>
                     <button onClick={() => navigate('/dashboard')} className={styles.backButton}>
                         Back to Dashboard
                     </button>
                 </div>
             </motion.div>
         );
    }

    // --- Main Render ---
    return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <StepIndicator currentStep="Analyze & Clean" />
            <div className={styles.header}>
                <h1>Data Analysis</h1>
                <div className={styles.statusDisplay}>{getStatusDisplay()}</div>
            </div>

            <div className={styles.mainGrid}>
                {/* Left Column */}
                <div className={styles.leftColumn}>
                    <section className={`${styles.card} ${styles.summaryCard}`}>
                        <h2>Analysis Summary</h2>
                        <RenderSummary />
                    </section>
                    <section className={styles.card}>
                        <h2>Data Preview</h2>
                        <RenderPreview />
                    </section>
                    <section className={`${styles.card} ${styles.actionsCard}`}>
                        <h2>Next Steps</h2>
                        <p>
                             {runStatus === 'SUCCESS'
                                ? 'Review the summary and preview. Proceed to clean the data or skip to configuration if no major issues are found.'
                                : ['FAILED', 'ANALYSIS_FAILED', 'FETCH_FAILED'].includes(runStatus)
                                  ? 'Analysis failed. Please check the logs and consider uploading a corrected dataset.'
                                  : ['ANALYZING', 'STARTING', 'JOINING_ROOM', 'PENDING_TRIGGER', 'CONNECTING'].includes(runStatus)
                                     ? 'Analysis is in progress. Please wait for completion.'
                                     : 'Analysis status unknown or not started.'
                            }
                        </p>
                        <button
                            onClick={() => navigate(`/run/${runId}/clean`)}
                            disabled={runStatus !== 'SUCCESS'}
                            className={styles.primaryButton}
                        >
                            <span>Proceed to Data Cleaning</span>
                            <FontAwesomeIcon icon={faArrowRight} />
                        </button>
                        <button
                           onClick={() => navigate(`/run/${runId}/configure`)}
                           disabled={runStatus !== 'SUCCESS'}
                           className={styles.secondaryButton}
                        >
                           Skip Cleaning & Configure Training
                        </button>
                    </section>
                </div>

                {/* Right Column (Logs) */}
                <section className={`${styles.card} ${styles.logsCardContainer}`}>
                    <h2>Analysis Log</h2>
                    <div className={styles.logsContainer}>
                        {logs.map((log, index) => <LogLine key={`${log.timestamp}-${index}`} log={log} />)}
                        <div ref={logsEndRef} />
                    </div>
                </section>
            </div>
        </motion.div>
    );
};

export default AnalyzeData;