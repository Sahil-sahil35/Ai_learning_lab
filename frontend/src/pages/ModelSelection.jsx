import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faSpinner, faExclamationCircle, faBrain, faTree, faRocket,
  faEye, faLanguage, faVolumeUp, faMagic, faPlus
} from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';
import api from '../lib/api';
import styles from './ModelSelection.module.css'; // Import CSS Module
import Spinner from '../components/Spinner'; // Import Spinner

// Icon mapping (keep as before)
const iconMap = {
  "fas fa-spinner": faSpinner, "fas fa-exclamation-circle": faExclamationCircle,
  "fas fa-brain": faBrain, "fas fa-tree": faTree, "fas fa-rocket": faRocket,
  "fas fa-eye": faEye, "fas fa-language": faLanguage, "fas fa-volume-up": faVolumeUp,
  "fas fa-magic": faMagic, "fas fa-plus": faPlus,
};

// --- ModelCard Component (Internal) ---
const ModelCard = ({ model, onSelect }) => {
  const getTagStyle = (tag) => {
    const lowerTag = tag.toLowerCase();
    if (lowerTag === 'beginner') return styles.tagBeginner;
    if (lowerTag === 'intermediate') return styles.tagIntermediate;
    if (lowerTag === 'advanced') return styles.tagAdvanced;
    if (lowerTag.includes('class')) return styles.tagClassification;
    if (lowerTag.includes('regress')) return styles.tagRegression;
    // Add more specific tag styles if needed
    return styles.tagDefault;
  };

  const iconObject = iconMap[model.icon] || faBrain;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -5 }} // Removed boxShadow, handled by CSS :hover
      className={styles.modelCard} // Main card style
    >
      <div className={styles.cardHeader}>
        <div className={styles.cardIconWrapper}>
          <FontAwesomeIcon icon={iconObject} className={styles.cardIcon} />
        </div>
        <div className={styles.cardTags}>
          {(model.tags || []).slice(0, 2).map(tag => (
            <span key={tag} className={`${styles.tag} ${getTagStyle(tag)}`}>
              {tag}
            </span>
          ))}
        </div>
      </div>
      <div className={styles.cardBody}>
        <h3 className={styles.cardTitle}>{model.name}</h3>
        <p className={styles.cardDescription}>{model.description}</p>
      </div>
      <div className={styles.cardFooter}>
        <button
          onClick={() => onSelect(model.id)}
          className={styles.selectButton}
        >
          Select Model
        </button>
      </div>
    </motion.div>
  );
};

// --- Main ModelSelection Component ---
const ModelSelection = () => {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [models, setModels] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        setIsLoading(true);
        const response = await api.get('/api/models');
        setModels(response.data);
        setError(null);
      } catch (err) {
        console.error("Error fetching models:", err);
        setError("Failed to load models. Please try again later.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchModels();
  }, []);

  const handleSelectModel = (modelId) => {
    navigate(`/task/${taskId}/model/${modelId}/upload`);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={styles.pageContainer}
    >
      <div className={styles.pageHeader}>
        <h1>Choose Your Model</h1>
        <p>
          Select a model to apply to your task. Each model is suited for different data types and problems.
        </p>
      </div>

      {isLoading && (
        <div className={styles.loadingState}>
           <Spinner size="large" /> {/* Use Spinner component */}
           <p>Loading available models...</p>
        </div>
      )}

      {error && (
        <div className={styles.errorState}>
          <FontAwesomeIcon icon={faExclamationCircle} size="3x" />
          <p>{error}</p>
        </div>
      )}

      {!isLoading && !error && (
        <div className={styles.modelGrid}>
          {Array.isArray(models) && models.map(model => (
            <ModelCard key={model.id} model={model} onSelect={handleSelectModel} />
          ))}
          {/* Add placeholder card if needed for grid layout */}
        </div>
      )}
    </motion.div>
  );
};

export default ModelSelection;