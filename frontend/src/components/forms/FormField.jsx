// frontend/src/components/forms/FormField.jsx
import React from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faQuestionCircle } from '@fortawesome/free-solid-svg-icons';
// Use the CSS module from ConfigureTrain for consistency, or create a dedicated one
import styles from '../../pages/ConfigureTrain.module.css';

const FormField = ({ param, value, onChange, columnNames = [] }) => {
    const { name, label, type, options, placeholder, help, default: defaultValue, min, max, step } = param;

    const handleChange = (e) => {
        let val = e.target.value;
        // Convert type based on param definition
        if (type === 'number') {
            // Allow empty string to represent null/cleared value
            val = e.target.value === '' ? null : Number(e.target.value);
            // Optional: Clamp value based on min/max if needed
            if (val !== null) {
                if (min !== undefined && val < min) val = min;
                if (max !== undefined && val > max) val = max;
            }
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
                {/* Tooltip */}
                {help && (
                    <span className={styles.tooltipWrapper} title={help}>
                        <FontAwesomeIcon icon={faQuestionCircle} className={styles.tooltipIcon} />
                    </span>
                )}
            </label>

            {/* Render different input types */}
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
                     value={value ?? ''} // Use empty string for null/undefined
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
                      className={styles.checkboxField} // Add specific checkbox styles if needed
                  />
             )}

            {/* Display help text below input */}
            {help && <p className={styles.helpText}>{help}</p>}
        </div>
    );
};

export default FormField;