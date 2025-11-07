from flask import Blueprint, request, jsonify
from flask_limiter.util import get_remote_address
from app.models_pkg import User
from app.schemas import user_schema
from app import db, bcrypt, limiter
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import datetime
from services.email_service import email_service
import secrets

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/signup', methods=['POST'])
@limiter.limit("3 per hour")  # Limit registration attempts
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

        # Generate email verification token
        verification_token = secrets.token_urlsafe(32)
        new_user.set_email_verification_token(verification_token)

        db.session.add(new_user)
        db.session.commit()

        # Send verification email
        email_sent = email_service.send_verification_email(
            new_user.email,
            new_user.username,
            verification_token
        )

        # Note: Don't create access token until email is verified
        return jsonify({
            "msg": "User created successfully. Please check your email to verify your account.",
            "email_sent": email_sent,
            "user": user_schema.dump(new_user)
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Could not create user", "error": str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per 15 minutes")  # Limit login attempts
def login():
    """
    Log in an existing user.
    """
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"msg": "Email and password are required"}), 400

    user = User.query.filter_by(email=data['email']).first()

    if user and user.check_password(data['password']):
        # Check if email is verified
        if not user.email_verified:
            return jsonify({
                "msg": "Please verify your email address before logging in",
                "email_verified": False,
                "email": user.email
            }), 403

        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()

        access_token = create_access_token(identity=str(user.id))
        user_data = user_schema.dump(user)

        # Add role to response
        user_data['role'] = user.role.value if hasattr(user, 'role') else 'student'
        user_data['email_verified'] = user.email_verified

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
    user_data['email_verified'] = user.email_verified

    return jsonify(user_data), 200

@auth_bp.route('/verify-email', methods=['POST'])
@limiter.limit("10 per hour")
def verify_email():
    """Verify email address using token."""
    data = request.get_json()
    if not data or not data.get('token'):
        return jsonify({"msg": "Verification token is required"}), 400

    token = data['token']

    # Find user with this verification token
    user = User.query.filter_by(email_verification_token=token).first()

    if not user:
        return jsonify({"msg": "Invalid verification token"}), 400

    if user.verify_email(token):
        db.session.commit()

        # Send welcome email
        try:
            email_service.send_welcome_email(user.email, user.username)
        except Exception as e:
            # Log error but don't fail the verification
            print(f"Failed to send welcome email: {e}")

        # Create access token for newly verified user
        access_token = create_access_token(identity=str(user.id))
        user_data = user_schema.dump(user)
        user_data['role'] = user.role.value if hasattr(user, 'role') else 'student'
        user_data['email_verified'] = True

        return jsonify({
            "msg": "Email verified successfully! Welcome to AI Learning Lab!",
            "access_token": access_token,
            "user": user_data
        }), 200
    else:
        return jsonify({"msg": "Invalid or expired verification token"}), 400

@auth_bp.route('/resend-verification', methods=['POST'])
@limiter.limit("3 per hour")
def resend_verification():
    """Resend email verification."""
    data = request.get_json()
    if not data or not data.get('email'):
        return jsonify({"msg": "Email is required"}), 400

    email = data['email']
    user = User.query.filter_by(email=email).first()

    if not user:
        # Don't reveal if email exists or not
        return jsonify({"msg": "If your email exists in our system, you'll receive a verification email."}), 200

    if user.email_verified:
        return jsonify({"msg": "Email is already verified"}), 400

    # Generate new verification token
    verification_token = secrets.token_urlsafe(32)
    user.set_email_verification_token(verification_token)
    db.session.commit()

    # Send verification email
    email_sent = email_service.send_verification_email(
        user.email,
        user.username,
        verification_token
    )

    return jsonify({
        "msg": "Verification email sent. Please check your inbox.",
        "email_sent": email_sent
    }), 200

@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per hour")
def forgot_password():
    """Request password reset."""
    data = request.get_json()
    if not data or not data.get('email'):
        return jsonify({"msg": "Email is required"}), 400

    email = data['email']
    user = User.query.filter_by(email=email).first()

    if not user:
        # Don't reveal if email exists or not
        return jsonify({"msg": "If your email exists in our system, you'll receive a password reset email."}), 200

    # Generate password reset token
    reset_token = secrets.token_urlsafe(32)
    user.set_password_reset_token(reset_token)
    db.session.commit()

    # Send password reset email
    email_sent = email_service.send_password_reset_email(
        user.email,
        user.username,
        reset_token
    )

    return jsonify({
        "msg": "Password reset email sent. Please check your inbox.",
        "email_sent": email_sent
    }), 200

@auth_bp.route('/reset-password', methods=['POST'])
@limiter.limit("10 per hour")
def reset_password():
    """Reset password using token."""
    data = request.get_json()
    if not data or not all(k in data for k in ['token', 'password']):
        return jsonify({"msg": "Reset token and new password are required"}), 400

    token = data['token']
    new_password = data['password']

    # Find user with this reset token
    user = User.query.filter_by(password_reset_token=token).first()

    if not user:
        return jsonify({"msg": "Invalid reset token"}), 400

    if not user.verify_password_reset_token(token):
        return jsonify({"msg": "Invalid or expired reset token"}), 400

    # Update password
    user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
    user.clear_password_reset_token()
    db.session.commit()

    return jsonify({"msg": "Password reset successfully. You can now log in with your new password."}), 200