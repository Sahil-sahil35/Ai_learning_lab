from flask import Blueprint, jsonify
from ..services.model_registry import get_available_models
from flask_jwt_extended import jwt_required

models_bp = Blueprint('models_bp', __name__)

@models_bp.route('/', methods=['GET'])
@jwt_required()
def get_models():
    """
    Get the list of all available ML models from the registry.
    This route is protected, only logged-in users can see models.
    """
    try:
        models = get_available_models()
        return jsonify(models), 200
    except Exception as e:
        return jsonify({"msg": "Error fetching models", "error": str(e)}), 500