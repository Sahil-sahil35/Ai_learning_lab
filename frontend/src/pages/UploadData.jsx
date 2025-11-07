import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCloudUploadAlt, faFileCsv, faFileZipper, faSpinner, faCheckCircle } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';

import StepIndicator from '../components/StepIndicator';
import api from '../lib/api';
import styles from './UploadData.module.css'; // Import CSS Module
import Spinner from '../components/Spinner'; // Import Spinner

const UploadData = () => {
  const { taskId, modelId } = useParams();
  const navigate = useNavigate();
  const [modelConfig, setModelConfig] = useState(null);
  const [file, setFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingConfig, setIsFetchingConfig] = useState(true); // Added state

  // Fetch model config
  useEffect(() => {
    setIsFetchingConfig(true);
    api.get('/api/models')
      .then(res => {
        const foundModel = res.data.find(m => m.id === modelId);
        if (foundModel) {
          setModelConfig(foundModel);
        } else {
          toast.error('Model configuration not found.');
          navigate(`/task/${taskId}/select-model`);
        }
      })
      .catch(() => toast.error('Failed to load model details.'))
      .finally(() => setIsFetchingConfig(false)); // Set loading false
  }, [modelId, taskId, navigate]);

  // Dropzone setup
  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
        setFile(acceptedFiles[0]);
    } else {
        toast.error("File type not accepted or upload failed.");
    }
  }, []);

  // Determine accepted file types based on model config
  const acceptedFileTypes = {
      'tabular': { 'text/csv': ['.csv'] },
      'image_zip': { 'application/zip': ['.zip'] },
      // Add more types as needed
  };
  const acceptConfig = modelConfig ? acceptedFileTypes[modelConfig.data_type] : {};


  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: acceptConfig, // Use dynamic accept config
  });

  // Handle file upload to backend
  const handleUpload = async () => {
    // ... (keep existing logic) ...
     if (!file) {
      toast.error('Please select a file to upload.');
      return;
    }
    setIsLoading(true);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('model_id', modelId);

    try {
      const response = await api.post(`/training/${taskId}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const newRun = response.data;
      toast.success('File uploaded! Starting analysis...');

      navigate(`/run/${newRun.id}/analyze`);

    } catch (error) {
      const errorMsg = error.response?.data?.msg || 'Upload failed.';
      toast.error(errorMsg);
      setIsLoading(false);
    }
  };

  // Get appropriate icon
  const getFileIcon = () => {
    if (modelConfig?.data_type === 'image_zip') return faFileZipper;
    // Add more icons for other types
    return faFileCsv; // Default
  };

  // Loading state while fetching config
  if (isFetchingConfig || !modelConfig) {
    return (
      <div className={styles.loadingContainer}>
        <Spinner size="large" />
      </div>
    );
  }

  // Helper to format data type string
  const formatDataType = (type) => type?.replace('_', ' ') || 'data';


  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <StepIndicator currentStep="Upload Data" />

      <div className={styles.gridContainer}>

        {/* --- Left Column: Upload --- */}
        <div className={styles.card}>
          <h1>Upload Your Data</h1>
          <p className={styles.subtitle}>
            Upload the dataset for your <span className={styles.modelName}>{modelConfig.name}</span> model.
          </p>

          {/* Dropzone Area */}
          <div
            {...getRootProps()}
            className={`${styles.dropzone} ${isDragActive ? styles.dropzoneActive : ''}`}
          >
            <input {...getInputProps()} />
            <FontAwesomeIcon icon={faCloudUploadAlt} className={styles.dropzoneIcon} />
            {isDragActive ? (
              <p className={styles.dropzoneTextActive}>Drop the file here...</p>
            ) : (
              <p className={styles.dropzoneText}>
                Drag & drop your {formatDataType(modelConfig.data_type)} file here, or click to select
              </p>
            )}
             <p className={styles.dropzoneHint}>
                Accepted: {Object.values(acceptConfig || {}).flat().join(', ') || 'any'}
             </p>
          </div>

          {/* Selected File Info */}
          {file && (
            <div className={styles.fileInfo}>
              <div className={styles.fileInfoContent}>
                <FontAwesomeIcon icon={faCheckCircle} />
                <span>{file.name}</span>
              </div>
              <span className={styles.fileSize}>{(file.size / 1024 / 1024).toFixed(2)} MB</span>
            </div>
          )}

          {/* Upload Button */}
          <button
            onClick={handleUpload}
            disabled={!file || isLoading}
            className={styles.uploadButton}
          >
            {isLoading ? <FontAwesomeIcon icon={faSpinner} spin /> : null}
            {isLoading ? 'Uploading...' : 'Upload & Analyze Data'}
          </button>
        </div>

        {/* --- Right Column: Instructions --- */}
        <div className={styles.card}>
          <h2>Data Format Requirements</h2>
          <div className={styles.instructionsContainer}>
            {/* File Type Info */}
            <div className={styles.instructionItem}>
              <FontAwesomeIcon icon={getFileIcon()} className={styles.instructionIcon} />
              <div>
                <h3>File Type</h3>
                <p>This model requires a <strong>{formatDataType(modelConfig.data_type)}</strong> file.</p>
              </div>
            </div>

            {/* Dynamic Structure Info */}
            <div className={styles.structureInfo}>
              {modelConfig.data_type === 'tabular' && (
                <>
                  <h4>Tabular (CSV) Structure:</h4>
                  <ul>
                    <li>Must be a `.csv` file.</li>
                    <li>First row must be a header with column names.</li>
                    <li>Requires a 'target' column to predict.</li>
                    <li>Other columns are 'features'.</li>
                  </ul>
                </>
              )}
              {modelConfig.data_type === 'image_zip' && (
                <>
                  <h4>Image (ZIP) Structure:</h4>
                  <p>Your `.zip` must contain `train` and `val` folders, with class subfolders:</p>
                  <pre className={styles.codeBlock}>
                    {`your_data.zip/
                        ├── train/
                        │   ├── class_A/
                        │   │   ├── img1.jpg
                        │   │   └── img2.png
                        │   └── class_B/
                        │       ├── img3.jpg
                        │       └── ...
                        └── val/
                            ├── class_A/
                            └── class_B/`}
                  </pre>
                </>
              )}
               {/* Add instructions for other data_types here */}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default UploadData;