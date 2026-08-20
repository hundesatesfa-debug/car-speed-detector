import re
import logging
from flask import Blueprint, request, jsonify
import jwt
import datetime
from backend.config import Config
from backend.utils.security import check_password, hash_password
from backend.database import (
    execute_query, execute_insert, execute_update,
    is_token_blacklisted, blacklist_token,
)

security_logger = logging.getLogger("security")

auth_bp = Blueprint("auth", __name__)

_failed_attempts = {}


def _record_failed_login(username, ip):
    key = f"{username}:{ip}"
    now = time.time()
    if key not in _failed_attempts:
        _failed_attempts[key] = []
    _failed_attempts[key].append(now)
    cutoff = now - (Config.LOGIN_LOCKOUT_MINUTES * 60)
    _failed_attempts[key] = [t for t in _failed_attempts[key] if t > cutoff]
    return len(_failed_attempts[key])


def _is_locked_out(username, ip):
    key = f"{username}:{ip}"
    attempts = _failed_attempts.get(key, [])
    cutoff = time.time() - (Config.LOGIN_LOCKOUT_MINUTES * 60)
    recent = [t for t in attempts if t > cutoff]
    return len(recent) >= Config.MAX_LOGIN_ATTEMPTS


import time


def generate_token(user_id, username, role):
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=Config.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")


def token_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "Token is missing"}), 401

        if is_token_blacklisted(token):
            return jsonify({"error": "Token has been revoked"}), 401

        try:
            data = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
            request.user = data
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        admins = execute_query(
            "SELECT id, status FROM admins WHERE id = %s",
            (data["user_id"],),
        )
        if not admins or admins[0]["status"] != "active":
            security_logger.warning(f"Inactive/disabled user accessed API: user_id={data.get('user_id')}")
            return jsonify({"error": "Account is disabled"}), 403

        return f(*args, **kwargs)

    return decorated


def role_required(*roles):
    from functools import wraps

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user_role = request.user.get("role")
            if user_role not in roles:
                security_logger.warning(
                    f"Unauthorized role access: user={request.user.get('username')} role={user_role} required={roles}"
                )
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    username = data.get("username", "")
    password = data.get("password", "")
    ip = request.remote_addr

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    if _is_locked_out(username, ip):
        security_logger.warning(f"Locked out login attempt: user={username} ip={ip}")
        return jsonify({"error": "Account temporarily locked due to too many failed attempts"}), 429

    admins = execute_query(
        "SELECT id, username, password_hash, role, status FROM admins WHERE username = %s",
        (username,),
    )

    if not admins or not check_password(password, admins[0]["password_hash"]):
        count = _record_failed_login(username, ip)
        remaining = Config.MAX_LOGIN_ATTEMPTS - count
        security_logger.warning(f"Failed login: user={username} ip={ip} attempts={count}")
        if remaining <= 0:
            return jsonify({"error": "Account temporarily locked due to too many failed attempts"}), 429
        return jsonify({"error": "Invalid credentials"}), 401

    admin = admins[0]

    if admin["status"] != "active":
        security_logger.warning(f"Disabled user login attempt: user={username} ip={ip}")
        return jsonify({"error": "Account is disabled"}), 403

    _failed_attempts.pop(f"{username}:{ip}", None)

    token = generate_token(admin["id"], admin["username"], admin["role"])
    security_logger.info(f"Successful login: user={username} ip={ip}")

    return jsonify({
        "token": token,
        "user": {
            "id": admin["id"],
            "username": admin["username"],
            "role": admin["role"],
        },
    })


@auth_bp.route("/me", methods=["GET"])
@token_required
def get_current_user():
    user = request.user
    admins = execute_query(
        "SELECT id, username, role, status, created_at FROM admins WHERE id = %s",
        (user["user_id"],),
    )
    if not admins:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": admins[0]})


@auth_bp.route("/update-profile", methods=["PUT"])
@token_required
def update_profile():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    user_id = request.user["user_id"]
    current_password = data.get("current_password", "")
    new_username = data.get("username", "")
    new_password = data.get("password", "")

    if not current_password:
        return jsonify({"error": "Current password is required"}), 400

    admins = execute_query(
        "SELECT id, password_hash FROM admins WHERE id = %s",
        (user_id,),
    )
    if not admins:
        return jsonify({"error": "User not found"}), 404

    if not check_password(current_password, admins[0]["password_hash"]):
        security_logger.warning(f"Failed profile update (wrong password): user_id={user_id}")
        return jsonify({"error": "Current password is incorrect"}), 403

    updates = []
    params = []

    if new_username:
        if not re.match(r"^[a-zA-Z0-9_]{3,30}$", new_username):
            return jsonify({"error": "Username must be 3-30 characters, alphanumeric and underscore only"}), 400
        existing = execute_query(
            "SELECT id FROM admins WHERE username = %s AND id != %s",
            (new_username, user_id),
        )
        if existing:
            return jsonify({"error": "Username already taken"}), 400
        updates.append("username = %s")
        params.append(new_username)

    if new_password:
        if len(new_password) < Config.MIN_PASSWORD_LENGTH:
            return jsonify({"error": f"Password must be at least {Config.MIN_PASSWORD_LENGTH} characters"}), 400
        if not re.search(r"[A-Z]", new_password):
            return jsonify({"error": "Password must contain an uppercase letter"}), 400
        if not re.search(r"[a-z]", new_password):
            return jsonify({"error": "Password must contain a lowercase letter"}), 400
        if not re.search(r"[0-9]", new_password):
            return jsonify({"error": "Password must contain a number"}), 400
        updates.append("password_hash = %s")
        params.append(hash_password(new_password))
        security_logger.info(f"Password changed for user_id={user_id}")

    if not updates:
        return jsonify({"error": "Nothing to update"}), 400

    params.append(user_id)
    execute_update(
        f"UPDATE admins SET {', '.join(updates)} WHERE id = %s",
        params,
    )

    updated_admin = execute_query(
        "SELECT id, username, role, status, created_at FROM admins WHERE id = %s",
        (user_id,),
    )

    return jsonify({
        "message": "Profile updated",
        "user": updated_admin[0],
    })


@auth_bp.route("/logout", methods=["POST"])
@token_required
def logout():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        blacklist_token(token)
        security_logger.info(f"User logged out: user={request.user.get('username')}")
    return jsonify({"message": "Logged out"})
