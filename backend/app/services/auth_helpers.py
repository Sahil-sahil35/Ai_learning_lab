from flask_jwt_extended import get_jwt_identity
from ..models_pkg import User

def get_user_from_token():
    """
    Helper function to get the full User object
    from the JWT token in a protected route.
    """
    user_id = get_jwt_identity()
    if not user_id:
        return None
    
    user = User.query.get(user_id)
    return user