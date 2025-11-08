// frontend/src/pages/ConfigureTrain.jsx

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSpinner, faPlay, faQuestionCircle } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';

import StepIndicator from '../components/StepIndicator';
import api from '../lib/api';
import styles from './ConfigureTrain.module.css';
import Spinner from '../components/Spinner';
import FullScreenStatus from '../components/FullScreenStatus';

// --- FormField Component (Keep as is) ---
const FormField = ({ param, value, onChange, columnNames = [] }) => {
    const { name, label, type, options, placeholder, help, default: defaultValue, min, max, step } = param;

    const handleChange = (e) => {
        let val = e.target.value;
        if (type === 'number') {
            val = e.target.value === '' ? null : Number(e.target.value);
        } else if (type === 'boolean_checkbox') {
             val = e.target.checked;
        }
        onChange(name, val);
    };

    const fieldId = `param-${name}`;

    return (
        <div className={styles.formField}>
            <label htmlFor={fieldId} className={styles.label}>
                {label}
                {help && (
                    <span className={styles.tooltipWrapper} title={help}>
                        <FontAwesomeIcon icon={faQuestionCircle} className={styles.tooltipIcon} />
                    </span>
                )}
            </label>

            {/* --- Updated Logic --- */}
            {type === 'target_column' && (
                <select id={fieldId} value={value ?? ''} onChange={handleChange} className={styles.selectField} required>
                    <option value="" disabled>Select target column...</option>
                    {columnNames.map(col => <option key={col} value={col}>{col}</option>)}
                </select>
            )}
            {type === 'select' && (
                 <select id={fieldId} value={value ?? defaultValue ?? ''} onChange={handleChange} className={styles.selectField}>
                     {(options || []).map(opt => <option key={opt} value={opt}>{opt}</option>)}
                 </select>
            )}
            {type === 'number' && (
                 <input
                     id={fieldId} type="number"
                     // Use empty string if value is null/undefined to avoid React warning
                     value={value ?? ''}
                     onChange={handleChange}
                     placeholder={placeholder ?? String(defaultValue ?? '')}
                     min={min} max={max} step={step}
                     className={styles.inputField}
                 />
            )}
             {type === 'text' && (
                 <input
                     id={fieldId} type="text"
                     value={value ?? ''}
                     onChange={handleChange}
                     placeholder={placeholder ?? String(defaultValue ?? '')}
                     className={styles.inputField}
                 />
             )}
             {type === 'boolean_checkbox' && (
                  <input
                      id={fieldId} type="checkbox"
                      checked={value ?? defaultValue ?? false}
                      onChange={handleChange}
                      className={styles.checkboxField} // Add styling for checkbox if needed
                  />
             )}
             {/* --- End Updated Logic --- */}

            {help && <p className={styles.helpText}>{help}</p>}
        </div>
    );
};

// --- Main ConfigureTrain Component ---
const ConfigureTrain = () => {
    const { runId } = useParams();
    const navigate = useNavigate();
    const [modelConfig, setModelConfig] = useState(null); // Model parameter definitions
    const [runDetails, setRunDetails] = useState(null); // Run details + analysis results
    const [columnNames, setColumnNames] = useState([]);
    const [params, setParams] = useState({}); // User-selected parameters
    const [isFetching, setIsFetching] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState(null); // Added error state

    // --- FIX: Fetch Run Details (includes analysis) and Model Config ---
    useEffect(() => {
        const fetchData = async () => {
          setIsFetching(true);
          setError(null); // Reset error on fetch
          try {
            // Fetch run details first to get modelId and analysis results
            const runRes = await api.get(`/training/run/${runId}`);
            setRunDetails(runRes.data);
            const modelId = runRes.data.model_id_str;

            // Fetch the parameter definitions for this model
            const modelsRes = await api.get('/models');
            const foundModel = modelsRes.data.find(m => m.id === modelId);

            if (!foundModel) throw new Error(`Model config not found for ID: ${modelId}`);
            setModelConfig(foundModel);

            // Set default parameters based on model config
            const defaultParams = {};
            foundModel.parameters.forEach(p => {
                // Handle null defaults appropriately, especially for selects/numbers
                let initialValue = p.default;
                if (p.type === 'number' && initialValue === null) initialValue = ''; // Use empty string for controlled number input
                if (p.type === 'select' && initialValue === null && p.options?.length > 0) initialValue = p.options[0]; // Default to first option? or ''
                if (p.type === 'boolean_checkbox' && initialValue === null) initialValue = false;
                defaultParams[p.name] = initialValue;
            });
            setParams(defaultParams);

            // Extract column names from analysis results
            const analysis = runRes.data.analysis_results;
            if (foundModel.data_type === 'tabular' && analysis?.basic_info?.columns) {
              setColumnNames(analysis.basic_info.columns);
            } else if (foundModel.data_type === 'tabular') {
                 // Handle case where analysis results are missing but expected
                 setError("Analysis results missing or incomplete. Cannot configure tabular model.");
                 setColumnNames([]); // Ensure it's empty
            }

          } catch (err) {
            setError('Failed to load configuration data. Please try again.');
            console.error("Fetch Error:", err);
            // Optionally redirect if critical data is missing
            // if (!modelConfig) navigate('/dashboard');
          } finally {
            setIsFetching(false);
          }
        };
        fetchData();
      }, [runId]);
      // --- END FIX ---


    const handleParamChange = (name, value) => {
        setParams(prev => ({ ...prev, [name]: value }));
    };

    const handleStartTraining = async (e) => {
        e.preventDefault();
        setIsSubmitting(true);
        toast.loading('Starting training job...');

        // Filter out null/empty values unless explicitly allowed (e.g., max_depth = null)
        const finalParams = {};
        for (const [key, value] of Object.entries(params)) {
            const paramConfig = modelConfig?.parameters.find(p => p.name === key);
            // Include if value is explicitly false (for checkbox), or not empty/null
            // Allow null specifically if the default was null and it's not a required field like target_column
            const isAllowedNull = paramConfig?.default === null && !['target_column'].includes(paramConfig?.type);

            if (value === false || (value !== null && value !== '') || (value === null && isAllowedNull)) {
                finalParams[key] = value;
            }
        }


        // Specific check for target column if needed by model
        const targetParamConfig = modelConfig?.parameters.find(p => p.type === 'target_column');
        if (targetParamConfig && !finalParams[targetParamConfig.name]) {
            toast.dismiss();
            toast.error(`Please select the '${targetParamConfig.label}' before starting.`);
            setIsSubmitting(false);
            return;
        }

        try {
            // Send finalParams to the backend
            await api.post(`/training/run/${runId}/train`, finalParams);
            toast.dismiss();
            toast.success('Training job started!');
            navigate(`/run/${runId}/training`);
        } catch (error) {
            toast.dismiss();
            const errorMsg = error.response?.data?.msg || 'Failed to start training.';
            toast.error(errorMsg);
            setIsSubmitting(false);
        }
    };

    // Loading and Error States
    if (isFetching || error) {
        return <FullScreenStatus isLoading={isFetching} error={error} loadingMessage="Loading configuration..." backLink={`/run/${runId}/clean`} />;
    }

    // Main Content
    if (!modelConfig || !runDetails) { // Should be caught by error state, but belt-and-suspenders
         return <div className={styles.loadingContainer}><p>Configuration data missing.</p></div>;
    }


    return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <StepIndicator currentStep="Configure" />

            <div className={styles.configContainer}>
                <h1>Configure Training</h1>
                <p className={styles.subtitle}>
                    Set the parameters for your <span className={styles.modelName}>{modelConfig.name}</span> model.
                </p>

                <form onSubmit={handleStartTraining} className={styles.formCard}>
                    <div className={styles.fieldsGrid}>
                        {modelConfig.parameters.map(param => (
                            <FormField
                                key={param.name}
                                param={param}
                                // Pass the current value from state, handle potential undefined
                                value={params[param.name]}
                                onChange={handleParamChange}
                                columnNames={columnNames}
                            />
                        ))}
                    </div>

                    <div className={styles.submitSection}>
                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className={styles.submitButton}
                        >
                            <FontAwesomeIcon icon={isSubmitting ? faSpinner : faPlay} spin={isSubmitting} />
                            <span>{isSubmitting ? 'Starting...' : 'Start Training'}</span>
                        </button>
                    </div>
                </form>
            </div>
        </motion.div>
    );
};

export default ConfigureTrain;