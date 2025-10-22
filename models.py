from flask_login import UserMixin
from functools import wraps
from flask import flash, abort
from flask_login import current_user

class User(UserMixin):
    def __init__(self, user_id, username, email, role, partner_id=None):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role
        self.partner_id = partner_id

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash("Доступ запрещён", "error")
                return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator