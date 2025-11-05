from flask import Blueprint, request, jsonify
from ..models import User
from ..schemas import user_schema
from .. import db, bcrypt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import datetime

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    Register a new user.
    """
    data = request.get_json()
    
    # Validation
    if not data or not data.get('email') or not data.get('password') or not data.get('username'):
        return jsonify({"msg": "Username, email, and password are required"}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({"msg": "Email already exists"}), 409
        
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"msg": "Username already exists"}), 409

    try:
        new_user = User(
            username=data['username'],
            email=data['email'],
            password=data['password']
        )
        db.session.add(new_user)
        db.session.commit()
        
        # Create an access token for the new user
        access_token = create_access_token(identity=str(new_user.id))
        
        return jsonify({
            "msg": "User created successfully",
            "access_token": access_token,
            "user": user_schema.dump(new_user)
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Could not create user", "error": str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Log in an existing user.
    """
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"msg": "Email and password are required"}), 400

    user = User.query.filter_by(email=data['email']).first()

    if user and user.check_password(data['password']):
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()

        access_token = create_access_token(identity=str(user.id))
        user_data = user_schema.dump(user)

        # Add role to response
        user_data['role'] = user.role.value if hasattr(user, 'role') else 'student'

        return jsonify({
            "msg": "Login successful",
            "access_token": access_token,
            "user": user_data
        }), 200
    else:
        return jsonify({"msg": "Invalid email or password"}), 401

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Get the profile of the currently logged-in user.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"msg": "User not found"}), 404

    user_data = user_schema.dump(user)
    # Add role to response
    user_data['role'] = user.role.value if hasattr(user, 'role') else 'student'
    user_data['is_active'] = user.is_active if hasattr(user, 'is_active') else True

    return jsonify(user_data), 200