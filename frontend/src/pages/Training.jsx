// frontend/src/pages/Training.jsx
import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSpinner, faCheckCircle, faTimesCircle, faPlay, faStop, faChartBar, faExclamationTriangle } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';
import api from '../lib/api';
import Spinner from '../components/Spinner';
import { connectSocket, disconnectSocket, joinTrainingRoom, leaveTrainingRoom } from '../lib/socket_enhanced';
import LiveLineChart from '../components/charts/LiveLineChart';
import StepIndicator from '../components/StepIndicator';
import styles from './Training.module.css';

const Training = () => {
    const { runId } = useParams();
    const navigate = useNavigate();
    const [runDetails, setRunDetails] = useState(null);
    const [taskType, setTaskType] = useState(null);
    const [runStatus, setRunStatus] = useState('LOADING_DETAILS');
    const [isFetchingDetails, setIsFetchingDetails] = useState(true);
    const [fetchError, setFetchError] = useState(null);
    const [logs, setLogs] = useState([]);
    const [metrics, setMetrics] = useState({});
    const [progress, setProgress] = useState({ epoch: 0, total_epochs: 0, step_name: 'Step', batch: 0, total_batches: 0 });

    const initialChartData = () => ({
        labels: [],
        datasets: [
            { label: 'Train', data: [], borderColor: 'var(--primary-500)', backgroundColor: 'rgba(87, 140, 250, 0.1)', tension: 0.1, fill: false, pointRadius: 1 },
            { label: 'Val', data: [], borderColor: 'var(--color-success)', backgroundColor: 'rgba(16, 185, 129, 0.1)', tension: 0.1, fill: false, pointRadius: 1 }
        ]
    });
    const [metricData, setMetricData] = useState({ primary: initialChartData(), secondary: initialChartData() });
    const [chartLabels, setChartLabels] = useState({ primary: 'Primary Metric', secondary: 'Secondary Metric / Loss' });

    const logsEndRef = useRef(null);
    const isMountedRef = useRef(true); // Ref to track component mount status

    // Effect to fetch initial run details
    useEffect(() => {
        isMountedRef.current = true;
        setIsFetchingDetails(true);
        setFetchError(null);
        api.get(`/training/run/${runId}`)
            .then(res => {
                if (!isMountedRef.current) return;
                const details = res.data;
                setRunDetails(details);
                setRunStatus(details.status || 'UNKNOWN');

                let determinedTaskType = 'classification';
                if (details.user_config?.task_type) {
                     determinedTaskType = details.user_config.task_type;
                } else if (details.educational_summary?.task_type) {
                    determinedTaskType = details.educational_summary.task_type;
                } else if (details.model_id_str?.includes('regressor') || details.model_id_str?.includes('regression')) {
                    determinedTaskType = 'regression';
                }
                setTaskType(determinedTaskType);
                console.log(`Training: Task type set to ${determinedTaskType}`);

                setChartLabels(determinedTaskType === 'regression'
                    ? { primary: 'R² Score', secondary: 'RMSE' }
                    : { primary: 'Accuracy', secondary: 'Loss' }
                );
            })
            .catch(err => {
                if (!isMountedRef.current) return;
                console.error("Failed to fetch run details:", err);
                const errorMsg = err.response?.data?.msg || "Could not load run details.";
                setFetchError(errorMsg);
                setRunStatus('FETCH_FAILED');
            })
            .finally(() => {
                if (isMountedRef.current) setIsFetchingDetails(false);
            });
        
        return () => {
             isMountedRef.current = false;
             console.log("Training: Unmounting, leaving room and disconnecting socket.");
             leaveTrainingRoom(runId);
             disconnectSocket();
        }
    }, [runId]);

    // Effect for scrolling logs
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    // WebSocket Effect
    useEffect(() => {
        if (isFetchingDetails || fetchError || !taskType) {
            return;
        }
        
        const isTerminal = ['SUCCESS', 'FAILED', 'FETCH_FAILED', 'CANCELLED'].includes(runStatus);
        if (isTerminal) {
            console.log("Run is in terminal state, not connecting socket.");
            return;
        }

        connectSocket();
        const onConnect = async () => {
            if (!isMountedRef.current) return;
            try {
                console.log('Socket connected for Training page');
                await joinTrainingRoom(runId);
                console.log(`Successfully joined training room: ${runId}`);
            } catch (error) {
                console.error('Failed to join training room:', error);
                setRunStatus('CONNECTING');
            }
        };
        const onDisconnect = (reason) => {
            if (!isMountedRef.current) return;
            console.log('Socket disconnected:', reason);
            if (['TRAINING', 'STARTING'].includes(runStatus)) {
                setRunStatus('CONNECTING');
                toast.error("Connection lost. Attempting to reconnect...");
            }
        };
        const onError = (err) => {
            if (!isMountedRef.current) return;
            console.error('Socket error:', err);
            toast.error(`Socket error: ${err.msg || 'Connection failed'}`);
        };
        const onStatus = (data) => {
             if (!isMountedRef.current) return;
             console.log(`Room status: ${data.msg}`);
        };

        const onLog = (log) => {
            if (!isMountedRef.current) return;
            if (!log.timestamp) log.timestamp = new Date().toISOString();
            setLogs(prevLogs => [...prevLogs, log]);
        };

        const onMetric = (metric) => {
            if (!isMountedRef.current || !taskType) return; 

            if (!metric.timestamp) metric.timestamp = new Date().toISOString();
            setMetrics(metric);

            const stepLabel = metric.epoch ?? metric.estimator ?? metric.iteration ?? progress.current_step ?? 0;
            const totalSteps = metric.total_epochs ?? metric.total_estimators ?? metric.total_iterations ?? progress.total_steps ?? 0;
            setProgress(prev => ({ ...prev, current_step: stepLabel, total_steps: totalSteps, step_name: metric.step_name || prev.step_name || 'Step' }));

            setMetricData(prev => {
                const newPrimary = structuredClone(prev.primary);
                const newSecondary = structuredClone(prev.secondary);
                const currentXValue = stepLabel;

                const isRegression = taskType === 'regression';
                const primaryTrainKey = isRegression ? 'train_r2' : 'train_accuracy';
                const primaryValKey = isRegression ? 'val_r2' : 'val_accuracy';
                const secondaryTrainKey = isRegression ? 'train_rmse' : 'train_loss';
                const secondaryValKey = isRegression ? 'val_rmse' : 'val_loss';

                let labelIndex = newPrimary.labels.indexOf(currentXValue);

                const trainP = metric[primaryTrainKey] ?? null;
                const valP = metric[primaryValKey] ?? null;
                const trainS = metric[secondaryTrainKey] ?? null;
                const valS = metric[secondaryValKey] ?? null;

                if (labelIndex > -1) {
                    newPrimary.datasets[0].data[labelIndex] = trainP;
                    newPrimary.datasets[1].data[labelIndex] = valP;
                    newSecondary.datasets[0].data[labelIndex] = trainS;
                    newSecondary.datasets[1].data[labelIndex] = valS;
                } else {
                     newPrimary.labels.push(currentXValue);
                     newSecondary.labels.push(currentXValue);
                     newPrimary.datasets[0].data.push(trainP);
                     newPrimary.datasets[1].data.push(valP);
                     newSecondary.datasets[0].data.push(trainS);
                     newSecondary.datasets[1].data.push(valS);
                }

                const maxPoints = 150;
                while (newPrimary.labels.length > maxPoints) {
                    newPrimary.labels.shift();
                    newSecondary.labels.shift();
                    newPrimary.datasets.forEach(ds => ds.data.shift());
                    newSecondary.datasets.forEach(ds => ds.data.shift());
                }

                return { primary: newPrimary, secondary: newSecondary };
            });
        };

        const onProgress = (prog) => {
             if (!isMountedRef.current) return;
             if (!prog.timestamp) prog.timestamp = new Date().toISOString();
            setProgress(prev => ({ ...prev, ...prog }));
        };

        const onStatusUpdate = (update) => {
             if (!isMountedRef.current) return;
            console.log("Received status update:", update.status);
            const newStatus = update.status;
            setRunStatus(newStatus);
            if (newStatus === 'SUCCESS') {
                toast.success('Training Completed Successfully!');
            } else if (newStatus === 'FAILED' || newStatus === 'ANALYSIS_FAILED' || newStatus === 'CLEANING_FAILED') {
                toast.error('Process Failed. Please check the logs.');
            } else if (newStatus === 'CANCELLED'){
                toast.success('Training stopped.');
            }
        };

        // Register Listeners
        socket.on('connect', onConnect);
        socket.on('disconnect', onDisconnect);
        socket.on('error', onError);
        socket.on('status', onStatus);
        socket.on('training_log', onLog);
        socket.on('training_metric', onMetric);
        socket.on('training_progress', onProgress);
        socket.on('status_update', onStatusUpdate);

        // --- START FIX [Issue #12] ---
        // Cleanup: Only leave the room.
        return () => {
            console.log("Training: Cleaning up WebSocket listeners and leaving room.");
            if (socket.connected) {
                leaveTrainingRoom(runId);
            }
            socket.off('connect', onConnect);
            socket.off('disconnect', onDisconnect);
            socket.off('error', onError);
            socket.off('status', onStatus);
            socket.off('training_log', onLog);
            socket.off('training_metric', onMetric);
            socket.off('training_progress', onProgress);
            socket.off('status_update', onStatusUpdate);
            // DO NOT call disconnectSocket() here
        };
        // --- END FIX ---
    }, [runId, isFetchingDetails, fetchError, taskType, runStatus]); // Add runStatus

    // Loading state for initial details fetch
    if (isFetchingDetails) {
        return (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <StepIndicator currentStep="Train" />
                <div className={styles.loadingContainer}>
                    <Spinner size="large" />
                    <p>Loading run details...</p>
                </div>
            </motion.div>
        );
    }

    // Error state for initial details fetch
    if (fetchError) {
         return (
             <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                 <StepIndicator currentStep="Train" />
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

    // --- RENDER FUNCTIONS ---

    // Function to display current status
    const getStatusDisplay = () => {
        switch (runStatus) {
            case 'TRAINING': return <span className={styles.statusTraining}><FontAwesomeIcon icon={faSpinner} spin className={styles.statusIcon} />Training in Progress...</span>;
            case 'STARTING': return <span className={styles.statusPending}><FontAwesomeIcon icon={faSpinner} spin className={styles.statusIcon} />Starting Training...</span>;
            case 'SUCCESS': return <span className={styles.statusSuccess}><FontAwesomeIcon icon={faCheckCircle} className={styles.statusIcon} />Training Successful!</span>;
            case 'FAILED':
            case 'ANALYSIS_FAILED':
            case 'CLEANING_FAILED':
                 return <span className={styles.statusFailed}><FontAwesomeIcon icon={faTimesCircle} className={styles.statusIcon} />Process Failed</span>;
             case 'CANCELLED':
                 return <span className={styles.statusFailed}><FontAwesomeIcon icon={faStop} className={styles.statusIcon} />Training Stopped</span>;
             // Show previous states if user navigates here
             case 'CLEANING': return <span className={styles.statusTraining}><FontAwesomeIcon icon={faSpinner} spin className={styles.statusIcon} />Cleaning Data...</span>;
             case 'CLEANING_SUCCESS': return <span className={styles.statusSuccess}><FontAwesomeIcon icon={faCheckCircle} className={styles.statusIcon} />Ready to Train</span>;
             case 'ANALYZING': return <span className={styles.statusTraining}><FontAwesomeIcon icon={faSpinner} spin className={styles.statusIcon} />Analyzing Data...</span>;
             case 'FETCH_FAILED': return <span className={styles.statusFailed}><FontAwesomeIcon icon={faTimesCircle} className={styles.statusIcon} />Load Failed</span>;
             case 'CONNECTING':
             case 'LOADING_DETAILS':
             case 'JOINING_ROOM':
             case 'PENDING_UPLOAD':
             case 'PENDING_ANALYSIS':
             case 'UNKNOWN':
            default: return <span className={styles.statusPending}><FontAwesomeIcon icon={faSpinner} spin className={styles.statusIcon} />Connecting/Waiting...</span>;
        }
    };

    // Log Line Component
    const LogLine = ({ log }) => {
        let lineStyle = styles.logLineInfo;
        let messageContent = log.message || '';
        const timestamp = log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '';
        let prefix = ''; // Use 'prefix' key if present, e.g. from stderr
        
        // Handle log_type from script first
        if (log.log_type === 'ERROR') lineStyle = styles.logLineError;
        else if (log.log_type === 'WARNING') lineStyle = styles.logLineWarning;
        else if (log.log_type === 'SUCCESS') lineStyle = styles.logLineSuccess;

        // Handle structured log types
        switch(log.type) {
            case 'ERROR': // Error from Celery task
                lineStyle = styles.logLineError;
                break;
            case 'metric':
                lineStyle = styles.logLineMetric;
                const stepLabel = log.epoch ?? log.estimator ?? log.iteration ?? '?';
                const totalSteps = log.total_epochs ?? log.total_estimators ?? log.total_iterations ?? '?';
                const metricsSummary = Object.entries(log)
                    .filter(([k, v]) => !['type', 'timestamp', 'epoch', 'estimator', 'iteration', 'total_epochs', 'total_estimators', 'total_iterations', 'step_name'].includes(k) && v !== null && v !== undefined)
                    .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${typeof v === 'number' ? v.toFixed(4) : v}`)
                    .join(' | ');
                messageContent = `[Step ${stepLabel}/${totalSteps}] Metrics: ${metricsSummary}`;
                break;
            case 'progress':
                lineStyle = styles.logLineProgress;
                const stepName = log.step_name || 'Step';
                const current = log.current_step ?? '?';
                const total = log.total_steps ?? '?';
                const batchInfo = (log.batch && log.total_batches) ? ` | Batch ${log.batch}/${log.total_batches}` : '';
                messageContent = `[Progress] ${stepName} ${current}/${total}${batchInfo}`;
                break;
            case 'CLIENT':
                lineStyle = styles.logLineClient;
                break;
            case 'analysis_result':
                 lineStyle = styles.logLineInfo;
                 messageContent = `[Data Structure] Received ${log.key || log.type}`;
                 break;
            case 'cleaning_report':
                 lineStyle = styles.logLineInfo;
                 messageContent = `[Data Structure] Received Cleaning Report`;
                 break;
            // Default 'log' type or unknown
            default:
                 messageContent = log.message || '';
                 // Check for script prefixes (like [script] or [stderr])
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

    // --- Main Render ---
    return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <StepIndicator currentStep="Train" />

            <div className={styles.header}>
                <div>
                    <h1>Live Training</h1>
                    <p>Model: <span className={styles.modelName}>{runDetails?.model_id_str?.replace(/_/g, ' ') || 'N/A'}</span> | Run ID: <span className={styles.runId}>{runId}</span></p>
                </div>
                <div className={styles.statusDisplay}>
                    {getStatusDisplay()}
                </div>
            </div>

            {/* Progress Card */}
            <div className={styles.progressCard}>
                <h3>Overall Progress ({progress.step_name || 'Steps'})</h3>
                <div className={styles.progressBarContainer}>
                    <motion.div
                        className={styles.progressBar}
                        // Animate width based on current_step vs total_steps
                        animate={{ width: `${((progress.epoch || progress.current_step || 0) / (progress.total_epochs || progress.total_steps || 1)) * 100}%` }}
                        transition={{ ease: "linear", duration: 0.2 }}
                    />
                </div>
                <div className={styles.progressText}>
                    <span>{progress.step_name || 'Step'}: {progress.epoch || progress.current_step || 0} / {progress.total_epochs || progress.total_steps || '?'}</span>
                    {(progress.batch > 0 || progress.total_batches > 0) &&
                       <span>Batch: {progress.batch || 0} / {progress.total_batches || '?'}</span>
                    }
                </div>

                {/* Conditional Buttons */}
                {runStatus === 'SUCCESS' && (
                    <motion.button
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                        onClick={() => navigate(`/run/${runId}/results`)}
                        className={styles.resultsButton}
                    >
                        <FontAwesomeIcon icon={faChartBar} />
                        <span>View Final Results</span>
                    </motion.button>
                )}
                {(runStatus === 'FAILED' || runStatus === 'ANALYSIS_FAILED' || runStatus === 'CLEANING_FAILED' || runStatus === 'CANCELLED') && (
                    <motion.button
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                        onClick={() => navigate('/dashboard')}
                        className={styles.backButton}
                    >
                        <span>Back to Dashboard</span>
                    </motion.button>
                )}
                { (runStatus === 'TRAINING' || runStatus === 'STARTING') && (
                     <button /* onClick={handleStopTraining} */ disabled className={styles.stopButton}>
                         <FontAwesomeIcon icon={faStop} /> Stop Training (Not Implemented)
                     </button>
                 )}
            </div>

            {/* Live Charts */}
            <div className={styles.chartsGrid}>
                <div className={styles.chartCard}>
                    <LiveLineChart title={chartLabels.primary} data={metricData.primary} />
                </div>
                <div className={styles.chartCard}>
                    <LiveLineChart title={chartLabels.secondary} data={metricData.secondary} />
                </div>
            </div>

            {/* Live Logs */}
            <div className={styles.logsCard}>
                <h3>Live Logs</h3>
                <div className={styles.logsContainer}>
                    {logs.map((log, index) => <LogLine key={`${log.timestamp}-${index}`} log={log} />)} {/* Use better key */}
                    <div ref={logsEndRef} />
                </div>
            </div>
        </motion.div>
    );
};

export default Training;