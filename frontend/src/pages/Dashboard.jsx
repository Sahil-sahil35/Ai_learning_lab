import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus, faSpinner, faExclamationCircle, faFolder, faChevronRight } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';
import api from '../lib/api';
import useAuthStore from '../lib/auth';
import styles from './Dashboard.module.css'; // Import the CSS Module
import Spinner from '../components/Spinner'; // Import Spinner for loading state

const Dashboard = () => {
  const user = useAuthStore((state) => state.user);
  const [tasks, setTasks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTasks = async () => {
      try {
        setIsLoading(true);
        const response = await api.get('/api/tasks');

        // Validate response data structure
        if (!response.data) {
          throw new Error('No data received from server');
        }

        const tasksData = Array.isArray(response.data) ? response.data : [];

        // Sort tasks by creation date, newest first
        const sortedTasks = tasksData.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        setTasks(sortedTasks);
        setError(null);
      } catch (err) {
        console.error("Error fetching tasks:", err);
        setError("Failed to load your tasks. Please try again later.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchTasks();
  }, []);

  // Helper to get status style class
  const getStatusClass = (status) => {
    switch (status) {
      case 'SUCCESS': return styles.statusSuccess;
      case 'FAILED': return styles.statusFailed;
      case 'ANALYSIS_FAILED': return styles.statusFailed; // Treat analysis fail same as fail
      case 'TRAINING':
      case 'ANALYZING':
      case 'STARTING': // Add starting status
        return styles.statusRunning;
      default: return styles.statusPending; // PENDING, PENDING_UPLOAD, PENDING_ANALYSIS etc.
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
      className={styles.dashboardContainer}
    >
      {/* --- Dashboard Header --- */}
      <div className={styles.header}>
        <h1>
          Welcome, {user?.username}!
        </h1>
        <Link to="/task/new" className={styles.newTaskButton}>
          <FontAwesomeIcon icon={faPlus} />
          <span>New Task</span>
        </Link>
      </div>

      {/* --- Task List Section --- */}
      <div className={styles.taskListContainer}>
        <h2 className={styles.taskListTitle}>Your Tasks</h2>

        {/* Loading State */}
        {isLoading && (
          <div className={styles.stateIndicator}>
            <Spinner size="medium" /> {/* Use Spinner component */}
            <p>Loading your tasks...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className={`${styles.stateIndicator} ${styles.errorState}`}>
            <FontAwesomeIcon icon={faExclamationCircle} size="2x" />
            <p>{error}</p>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && tasks.length === 0 && (
          <div className={styles.stateIndicator}>
            <FontAwesomeIcon icon={faFolder} className={styles.emptyIcon} />
            <h3>No tasks found.</h3>
            <p>Get started by creating your first ML task.</p>
            <Link to="/task/new" className={styles.newTaskButton}> {/* Reuse button style */}
              Create New Task
            </Link>
          </div>
        )}

        {/* Task List */}
        {!isLoading && !error && tasks.length > 0 && (
          <div className={styles.taskList}>
            {tasks.map(task => (
              <motion.div
                key={task.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={styles.taskCard}
              >
                {/* Task Header */}
                <div className={styles.taskCardHeader}>
                  <div>
                    <h3 className={styles.taskName}>{task.name}</h3>
                    <p className={styles.taskDescription}>{task.description || 'No description'}</p>
                    <p className={styles.taskDate}>
                      Created: {new Date(task.created_at).toLocaleString()}
                    </p>
                  </div>
                  <Link
                    to={`/task/${task.id}/select-model`}
                    className={styles.addModelButton}
                  >
                    <span>Add Model Run</span>
                    <FontAwesomeIcon icon={faPlus} />
                  </Link>
                </div>

                {/* Model Runs List (if any) */}
                {task.model_runs && task.model_runs.length > 0 && (
                  <div className={styles.modelRunsSection}>
                    <h4>Model Runs:</h4>
                    <div className={styles.modelRunsList}>
                      {task.model_runs.map(run => (
                        <Link
                          to={`/run/${run.id}/results`} // Link directly to results
                          key={run.id}
                          className={styles.modelRunItem}
                        >
                          <div>
                            <span className={styles.modelName}>{run.model_id_str.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
                            <span className={`${styles.statusBadge} ${getStatusClass(run.status)}`}>
                              [{run.status}]
                            </span>
                          </div>
                          <FontAwesomeIcon icon={faChevronRight} className={styles.modelRunChevron} />
                        </Link>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default Dashboard;