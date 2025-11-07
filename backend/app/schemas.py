from . import ma
from .models_pkg import User, Task, ModelRun

class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        # Exclude password_hash from all API responses
        exclude = ("password_hash",)
        include_fk = True

    # Add role field explicitly
    role = ma.Method('get_role')
    is_active = ma.Method('get_is_active')
    last_login = ma.Method('get_last_login')
    created_at = ma.Method('get_created_at')

    def get_role(self, obj):
        if hasattr(obj, 'role'):
            return obj.role.value
        return 'student'

    def get_is_active(self, obj):
        if hasattr(obj, 'is_active'):
            return obj.is_active
        return True

    def get_last_login(self, obj):
        if hasattr(obj, 'last_login') and obj.last_login:
            return obj.last_login.isoformat()
        return None

    def get_created_at(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return obj.created_at.isoformat()
        return None
        
user_schema = UserSchema()
users_schema = UserSchema(many=True)

class ModelRunSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ModelRun
        load_instance = True
        # Include nested task and user info
        include_fk = True
        
model_run_schema = ModelRunSchema()
model_runs_schema = ModelRunSchema(many=True)

class TaskSchema(ma.SQLAlchemyAutoSchema):
    # Nest all model runs within their parent task
    model_runs = ma.Nested(model_runs_schema, many=True)
    
    class Meta:
        model = Task
        load_instance = True
        include_fk = True

task_schema = TaskSchema()
tasks_schema = TaskSchema(many=True)