import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import api from '../lib/api';
import styles from './NewTask.module.css'; // Import CSS Module

const NewTask = () => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name) {
      toast.error('Task name is required.');
      return;
    }
    setIsLoading(true);

    try {
      const response = await api.post('/api/tasks', { name, description });
      const newTask = response.data;

      toast.success('Task created successfully!');

      // Navigate to the model selection page for this new task
      navigate(`/task/${newTask.id}/select-model`);

    } catch (error) {
      const errorMsg = error.response?.data?.msg || 'Failed to create task.';
      toast.error(errorMsg);
      setIsLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={styles.newTaskContainer}
    >
      <div className={styles.header}>
        <h1>Create a New Task</h1>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className={styles.formCard}
      >
        <form onSubmit={handleSubmit} className={styles.form}>
          {/* Task Name Field */}
          <div className={styles.inputGroup}>
            <label htmlFor="task-name" className={styles.label}>
              Task Name
            </label>
            <input
              type="text"
              id="task-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={styles.inputField}
              placeholder="e.g., Iris Flower Classification"
              required
            />
            <p className={styles.helpText}>This will be the name of your project.</p>
          </div>

          {/* Description Field */}
          <div className={styles.inputGroup}>
            <label htmlFor="task-description" className={styles.label}>
              Description (Optional)
            </label>
            <textarea
              id="task-description"
              rows="3"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={styles.textAreaField} // Use a different class if needed
              placeholder="A brief description of what you're trying to do..."
            />
          </div>

          {/* Submit Button */}
          <div className={styles.buttonContainer}>
            <button
              type="submit"
              disabled={isLoading}
              className={styles.submitButton}
            >
              {isLoading ? 'Creating...' : 'Create Task and Select Model'}
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
};

export default NewTask;