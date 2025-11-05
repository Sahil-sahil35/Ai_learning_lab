"""
Custom model development API routes for creating, validating,
training, and managing custom ML models.
"""

import datetime
import uuid
import os
import json
import tempfile
import shutil
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import desc, or_

from .. import db
from ..models import User
from ..models.enhanced import (
    CustomModel, CustomModelVersion, UserRole, CustomModelStatus
)
from ..middleware.security import security_monitor, InputValidator
from ..middleware.rate_limiter import rate_limit
from ..services.sandbox_executor import SandboxExecutor

custom_models_bp = Blueprint('custom_models', __name__, url_prefix='/api/custom-models')

@custom_models_bp.route('', methods=['POST'])
@jwt_required()
@rate_limit('api')
def create_custom_model():
    """Create a new custom model project."""
    try:
        data = request.get_json()
        user_id = get_jwt_identity()

        # Validate input
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        model_type = data.get('model_type', '').strip()
        template_id = data.get('template_id')

        # Input validation
        if not name or len(name) < 3:
            return jsonify({'error': 'Model name must be at least 3 characters long'}), 400

        if not model_type:
            return jsonify({'error': 'Model type is required'}), 400

        if not InputValidator.validate_json_input(data, ['name', 'model_type'])[0]:
            return jsonify({'error': 'Invalid input data'}), 400

        # Check if user has permission (students can create, admins have elevated limits)
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Check user's model count limits
        existing_models = CustomModel.query.filter_by(user_id=user_id).count()
        max_models = 50 if user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN] else 10

        if existing_models >= max_models:
            return jsonify({'error': f'Maximum model limit ({max_models}) reached'}), 429

        # Create custom model
        custom_model = CustomModel(
            user_id=user_id,
            name=name,
            description=description,
            model_type=model_type,
            template_id=uuid.UUID(template_id) if template_id else None,
            config=data.get('config', {}),
            tags=data.get('tags', []),
            is_public=data.get('is_public', False)
        )

        db.session.add(custom_model)
        db.session.commit()

        # Create initial version with template code or basic structure
        initial_code = _get_template_code(model_type, template_id)
        initial_version = CustomModelVersion(
            custom_model_id=custom_model.id,
            user_id=user_id,
            version_number=1,
            code_content=initial_code,
            config=data.get('config', {}),
            commit_message="Initial version created"
        )
        db.session.add(initial_version)
        db.session.commit()

        # Log creation
        security_monitor.log_security_event('custom_model_created', {
            'model_id': str(custom_model.id),
            'model_name': name,
            'model_type': model_type
        }, 'low')

        return jsonify({
            'message': 'Custom model created successfully',
            'model': {
                'id': str(custom_model.id),
                'name': custom_model.name,
                'description': custom_model.description,
                'model_type': custom_model.model_type,
                'status': custom_model.status.value,
                'created_at': custom_model.created_at.isoformat(),
                'is_public': custom_model.is_public
            }
        }), 201

    except Exception as e:
        current_app.logger.error(f"Error creating custom model: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create custom model'}), 500

@custom_models_bp.route('', methods=['GET'])
@jwt_required()
@rate_limit('api')
def get_custom_models():
    """Get list of user's custom models."""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        # Query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status_filter = request.args.get('status')
        model_type_filter = request.args.get('model_type')
        include_public = request.args.get('include_public', 'false').lower() == 'true'

        # Build query
        query = CustomModel.query

        # Admin can see all models, others see only their own
        if user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            query = query.filter(CustomModel.user_id == user_id)
        elif include_public:
            # Include public models from other users
            query = query.filter(
                or_(
                    CustomModel.user_id == user_id,
                    CustomModel.is_public == True
                )
            )
        else:
            query = query.filter(CustomModel.user_id == user_id)

        # Apply filters
        if status_filter:
            try:
                status_enum = CustomModelStatus(status_filter)
                query = query.filter(CustomModel.status == status_enum)
            except ValueError:
                pass

        if model_type_filter:
            query = query.filter(CustomModel.model_type == model_type_filter)

        # Order by last updated
        query = query.order_by(desc(CustomModel.updated_at))

        # Paginate
        paginated_models = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        models_data = []
        for model in paginated_models.items:
            model_data = {
                'id': str(model.id),
                'name': model.name,
                'description': model.description,
                'model_type': model.model_type,
                'status': model.status.value,
                'is_public': model.is_public,
                'tags': model.tags or [],
                'created_at': model.created_at.isoformat(),
                'updated_at': model.updated_at.isoformat(),
                'trained_at': model.trained_at.isoformat() if model.trained_at else None
            }

            # Add owner info (for admins viewing other users' models)
            if model.user_id != user_id:
                model_data['owner'] = {
                    'id': str(model.user.id),
                    'username': model.user.username
                }

            # Add version count
            model_data['versions_count'] = len(model.versions)

            models_data.append(model_data)

        return jsonify({
            'models': models_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated_models.total,
                'pages': paginated_models.pages,
                'has_next': paginated_models.has_next,
                'has_prev': paginated_models.has_prev
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching custom models: {e}")
        return jsonify({'error': 'Failed to fetch custom models'}), 500

@custom_models_bp.route('/<uuid:model_id>', methods=['GET'])
@jwt_required()
@rate_limit('api')
def get_custom_model(model_id):
    """Get detailed information about a custom model."""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        model = CustomModel.query.get_or_404(model_id)

        # Check permissions
        if (model.user_id != user_id and
            model.is_public == False and
            user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]):
            return jsonify({'error': 'Access denied'}), 403

        # Get latest version
        latest_version = model.versions.order_by(desc(CustomModelVersion.version_number)).first()

        model_data = {
            'id': str(model.id),
            'name': model.name,
            'description': model.description,
            'model_type': model.model_type,
            'status': model.status.value,
            'is_public': model.is_public,
            'tags': model.tags or [],
            'config': model.config or {},
            'created_at': model.created_at.isoformat(),
            'updated_at': model.updated_at.isoformat(),
            'trained_at': model.trained_at.isoformat() if model.trained_at else None,
            'training_metrics': model.training_metrics,
            'versions_count': len(model.versions)
        }

        # Add latest version code
        if latest_version:
            model_data['latest_version'] = {
                'version_number': latest_version.version_number,
                'code_content': latest_version.code_content,
                'config': latest_version.config or {},
                'commit_message': latest_version.commit_message,
                'created_at': latest_version.created_at.isoformat()
            }

        # Add owner info
        if model.user_id != user_id:
            model_data['owner'] = {
                'id': str(model.user.id),
                'username': model.user.username
            }

        return jsonify({'model': model_data})

    except Exception as e:
        current_app.logger.error(f"Error fetching custom model: {e}")
        return jsonify({'error': 'Failed to fetch custom model'}), 500

@custom_models_bp.route('/<uuid:model_id>/validate', methods=['POST'])
@jwt_required()
@rate_limit('api')
def validate_model_code(model_id):
    """Validate custom model code syntax and structure."""
    try:
        user_id = get_jwt_identity()

        model = CustomModel.query.get_or_404(model_id)

        # Check permissions
        if model.user_id != user_id:
            return jsonify({'error': 'Access denied'}), 403

        data = request.get_json()
        code_content = data.get('code_content', '')

        if not code_content:
            return jsonify({'error': 'Code content is required'}), 400

        # Update status to validating
        model.status = CustomModelStatus.VALIDATING
        db.session.commit()

        # Validate code in sandbox
        sandbox = SandboxExecutor()
        validation_result = sandbox.validate_code(
            code=code_content,
            model_type=model.model_type,
            config=data.get('config', {})
        )

        # Update model status based on validation
        if validation_result['valid']:
            model.status = CustomModelStatus.VALIDATED
        else:
            model.status = CustomModelStatus.DRAFT

        db.session.commit()

        # Log validation
        security_monitor.log_security_event('model_validation', {
            'model_id': str(model_id),
            'valid': validation_result['valid'],
            'errors': validation_result.get('errors', [])
        }, 'low')

        return jsonify({
            'valid': validation_result['valid'],
            'errors': validation_result.get('errors', []),
            'warnings': validation_result.get('warnings', []),
            'suggestions': validation_result.get('suggestions', [])
        })

    except Exception as e:
        current_app.logger.error(f"Error validating model code: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to validate model code'}), 500

@custom_models_bp.route('/<uuid:model_id>/train', methods=['POST'])
@jwt_required()
@rate_limit('training')
def train_custom_model(model_id):
    """Start training a custom model."""
    try:
        user_id = get_jwt_identity()

        model = CustomModel.query.get_or_404(model_id)

        # Check permissions
        if model.user_id != user_id:
            return jsonify({'error': 'Access denied'}), 403

        # Check if model is ready for training
        if model.status not in [CustomModelStatus.VALIDATED, CustomModelStatus.FAILED]:
            return jsonify({'error': 'Model must be validated before training'}), 400

        data = request.get_json()
        version_number = data.get('version_number', 1)
        training_config = data.get('config', {})
        data_path = data.get('data_path')

        if not data_path:
            return jsonify({'error': 'Training data path is required'}), 400

        # Get the specified version
        version = CustomModelVersion.query.filter_by(
            custom_model_id=model_id,
            version_number=version_number
        ).first()

        if not version:
            return jsonify({'error': f'Version {version_number} not found'}), 404

        # Update status to training
        model.status = CustomModelStatus.TRAINING
        db.session.commit()

        # Start training in sandbox
        sandbox = SandboxExecutor()
        training_job = sandbox.train_model(
            code=version.code_content,
            model_type=model.model_type,
            data_path=data_path,
            config=training_config,
            model_id=str(model.id)
        )

        # Store training job info
        model.training_data_path = data_path
        model.config = training_config

        # Log training start
        security_monitor.log_security_event('custom_model_training', {
            'model_id': str(model_id),
            'version': version_number,
            'job_id': training_job['job_id']
        }, 'medium')

        return jsonify({
            'message': 'Training started successfully',
            'job_id': training_job['job_id'],
            'estimated_duration': training_job.get('estimated_duration'),
            'model': {
                'id': str(model.id),
                'status': model.status.value
            }
        }), 202

    except Exception as e:
        current_app.logger.error(f"Error starting model training: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to start training'}), 500

@custom_models_bp.route('/<uuid:model_id>/files', methods=['GET', 'POST'])
@jwt_required()
@rate_limit('api')
def manage_model_files(model_id):
    """Manage model project files."""
    try:
        user_id = get_jwt_identity()

        model = CustomModel.query.get_or_404(model_id)

        # Check permissions
        if model.user_id != user_id:
            return jsonify({'error': 'Access denied'}), 403

        if request.method == 'GET':
            # List project files
            project_dir = Path(current_app.config['USER_UPLOADS_DIR']) / f'custom_models/{model_id}'

            if not project_dir.exists():
                return jsonify({'files': []})

            files = []
            for file_path in project_dir.rglob('*'):
                if file_path.is_file():
                    relative_path = file_path.relative_to(project_dir)
                    files.append({
                        'name': str(relative_path),
                        'size': file_path.stat().st_size,
                        'modified': datetime.datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                        'type': 'file' if file_path.is_file() else 'directory'
                    })

            return jsonify({'files': files})

        elif request.method == 'POST':
            # Upload file
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            # Create project directory
            project_dir = Path(current_app.config['USER_UPLOADS_DIR']) / f'custom_models/{model_id}'
            project_dir.mkdir(parents=True, exist_ok=True)

            # Save file
            file_path = project_dir / file.filename
            file.save(str(file_path))

            return jsonify({
                'message': 'File uploaded successfully',
                'file': {
                    'name': file.filename,
                    'size': file_path.stat().st_size
                }
            }), 201

    except Exception as e:
        current_app.logger.error(f"Error managing model files: {e}")
        return jsonify({'error': 'Failed to manage files'}), 500

@custom_models_bp.route('/<uuid:model_id>/deploy', methods=['POST'])
@jwt_required()
@rate_limit('api')
def deploy_custom_model(model_id):
    """Deploy a trained custom model for inference."""
    try:
        user_id = get_jwt_identity()

        model = CustomModel.query.get_or_404(model_id)

        # Check permissions
        if model.user_id != user_id:
            return jsonify({'error': 'Access denied'}), 403

        # Check if model is trained
        if model.status != CustomModelStatus.TRAINED:
            return jsonify({'error': 'Model must be trained before deployment'}), 400

        data = request.get_json()
        deployment_config = data.get('config', {})

        # Deploy model (simplified - in production would use proper deployment system)
        deployment_info = {
            'deployment_id': str(uuid.uuid4()),
            'model_id': str(model.id),
            'endpoint_url': f"/api/models/custom/{model_id}/predict",
            'deployed_at': datetime.datetime.utcnow().isoformat(),
            'status': 'active'
        }

        # Update model status
        model.status = CustomModelStatus.DEPLOYED
        db.session.commit()

        # Log deployment
        security_monitor.log_security_event('custom_model_deployed', {
            'model_id': str(model_id),
            'deployment_id': deployment_info['deployment_id']
        }, 'medium')

        return jsonify({
            'message': 'Model deployed successfully',
            'deployment': deployment_info
        })

    except Exception as e:
        current_app.logger.error(f"Error deploying model: {e}")
        return jsonify({'error': 'Failed to deploy model'}), 500

def _get_template_code(model_type: str, template_id: str = None) -> str:
    """Get template code for a given model type."""
    templates = {
        'classification': '''
# Classification Model Template
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

class CustomClassifier:
    def __init__(self, config=None):
        self.config = config or {}
        self.model = None
        self.features = None

    def load_data(self, data_path):
        """Load training data from CSV file."""
        self.data = pd.read_csv(data_path)
        return self.data

    def preprocess(self, target_column):
        """Preprocess the data."""
        # Handle missing values
        self.data = self.data.fillna(self.data.mean())

        # Separate features and target
        self.features = self.data.drop(columns=[target_column])
        self.target = self.data[target_column]

        # Convert categorical variables
        self.features = pd.get_dummies(self.features)

        return self.features, self.target

    def train(self, test_size=0.2, random_state=42):
        """Train the classification model."""
        X_train, X_test, y_train, y_test = train_test_split(
            self.features, self.target, test_size=test_size, random_state=random_state
        )

        # Initialize and train model
        self.model = RandomForestClassifier(
            n_estimators=self.config.get('n_estimators', 100),
            random_state=random_state
        )
        self.model.fit(X_train, y_train)

        # Evaluate model
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        metrics = {
            'accuracy': accuracy,
            'classification_report': classification_report(y_test, y_pred)
        }

        return metrics

    def predict(self, X):
        """Make predictions."""
        if self.model is None:
            raise ValueError("Model not trained yet")
        return self.model.predict(X)

    def save_model(self, path):
        """Save the trained model."""
        joblib.dump(self.model, path)

# Training function (required by the platform)
def train_model(data_path, config=None, output_dir=None):
    """Main training function."""
    model = CustomClassifier(config)

    # Load and preprocess data
    model.load_data(data_path)
    target_column = config.get('target_column', 'target')
    features, target = model.preprocess(target_column)

    # Train model
    metrics = model.train()

    # Save model
    if output_dir:
        model.save_model(f"{output_dir}/model.joblib")

    return metrics
''',
        'regression': '''
# Regression Model Template
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib

class CustomRegressor:
    def __init__(self, config=None):
        self.config = config or {}
        self.model = None
        self.features = None

    def load_data(self, data_path):
        """Load training data from CSV file."""
        self.data = pd.read_csv(data_path)
        return self.data

    def preprocess(self, target_column):
        """Preprocess the data."""
        # Handle missing values
        self.data = self.data.fillna(self.data.mean())

        # Separate features and target
        self.features = self.data.drop(columns=[target_column])
        self.target = self.data[target_column]

        # Convert categorical variables
        self.features = pd.get_dummies(self.features)

        return self.features, self.target

    def train(self, test_size=0.2, random_state=42):
        """Train the regression model."""
        X_train, X_test, y_train, y_test = train_test_split(
            self.features, self.target, test_size=test_size, random_state=random_state
        )

        # Initialize and train model
        self.model = RandomForestRegressor(
            n_estimators=self.config.get('n_estimators', 100),
            random_state=random_state
        )
        self.model.fit(X_train, y_train)

        # Evaluate model
        y_pred = self.model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        metrics = {
            'mse': mse,
            'rmse': np.sqrt(mse),
            'r2_score': r2
        }

        return metrics

    def predict(self, X):
        """Make predictions."""
        if self.model is None:
            raise ValueError("Model not trained yet")
        return self.model.predict(X)

    def save_model(self, path):
        """Save the trained model."""
        joblib.dump(self.model, path)

# Training function (required by the platform)
def train_model(data_path, config=None, output_dir=None):
    """Main training function."""
    model = CustomRegressor(config)

    # Load and preprocess data
    model.load_data(data_path)
    target_column = config.get('target_column', 'target')
    features, target = model.preprocess(target_column)

    # Train model
    metrics = model.train()

    # Save model
    if output_dir:
        model.save_model(f"{output_dir}/model.joblib")

    return metrics
'''
    }

    return templates.get(model_type, templates['classification'])