import os
import logging
from flask import Blueprint, request, jsonify
from backend.routes.auth import token_required, role_required
from backend.database import execute_query, execute_insert, execute_update
from backend.config import Config
from backend.app import limiter

security_logger = logging.getLogger("security")

cameras_bp = Blueprint("cameras", __name__)


def _validate_video_path(video_source):
    if video_source is None:
        return Config.VIDEO_PATH
    if os.path.isabs(video_source):
        raise ValueError("Absolute paths not allowed")
    if ".." in video_source:
        raise ValueError("Path traversal not allowed")
    full = os.path.normpath(os.path.join(Config.PROJECT_ROOT, video_source))
    if not full.startswith(os.path.normpath(Config.PROJECT_ROOT)):
        raise ValueError("Path outside project directory")
    if not os.path.exists(full):
        raise ValueError("File not found")
    return full


@cameras_bp.route("", methods=["GET"])
@token_required
def list_cameras():
    cameras = execute_query("SELECT * FROM cameras ORDER BY created_at DESC")
    return jsonify({"cameras": cameras})


@cameras_bp.route("/<int:camera_id>", methods=["GET"])
@token_required
def get_camera(camera_id):
    cameras = execute_query("SELECT * FROM cameras WHERE id = %s", (camera_id,))
    if not cameras:
        return jsonify({"error": "Camera not found"}), 404
    return jsonify({"camera": cameras[0]})


@cameras_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
@limiter.limit(Config.RATE_LIMIT_API)
def add_camera():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Camera name is required"}), 400
    if len(name) > 100:
        return jsonify({"error": "Camera name too long"}), 400

    location = data.get("location", "").strip()
    if len(location) > 200:
        return jsonify({"error": "Location too long"}), 400

    speed_limit = data.get("speed_limit", 50)
    try:
        speed_limit = int(speed_limit)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid speed limit"}), 400
    if speed_limit < 1 or speed_limit > 300:
        return jsonify({"error": "Speed limit must be between 1 and 300 km/h"}), 400

    distance = data.get("measurement_distance", 10.0)
    try:
        distance = float(distance)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid measurement distance"}), 400
    if distance < 1 or distance > 1000:
        return jsonify({"error": "Distance must be between 1 and 1000 meters"}), 400

    import secrets as _secrets
    camera_code = data.get("camera_code", f"CAM-{_secrets.token_hex(3).upper()}")

    camera_id = execute_insert(
        """INSERT INTO cameras
           (camera_code, camera_name, location, speed_limit, measurement_distance, status)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (camera_code, name, location, speed_limit, distance, "active"),
    )

    camera = execute_query("SELECT * FROM cameras WHERE id = %s", (camera_id,))
    security_logger.info(f"Camera created: id={camera_id} name={name} by={request.user.get('username')}")
    return jsonify({"camera": camera[0]}), 201


@cameras_bp.route("/<int:camera_id>", methods=["PUT"])
@token_required
@role_required("admin")
def update_camera(camera_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    cameras = execute_query("SELECT id FROM cameras WHERE id = %s", (camera_id,))
    if not cameras:
        return jsonify({"error": "Camera not found"}), 404

    allowed_fields = ["camera_name", "location", "speed_limit", "measurement_distance", "status"]
    fields = []
    values = []

    for field in allowed_fields:
        if field in data:
            val = data[field]
            if field == "speed_limit":
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    return jsonify({"error": "Invalid speed limit"}), 400
                if val < 1 or val > 300:
                    return jsonify({"error": "Speed limit must be between 1 and 300 km/h"}), 400
            elif field == "measurement_distance":
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    return jsonify({"error": "Invalid measurement distance"}), 400
                if val < 1 or val > 1000:
                    return jsonify({"error": "Distance must be between 1 and 1000 meters"}), 400
            elif field == "status":
                if val not in ("active", "disabled"):
                    return jsonify({"error": "Invalid status"}), 400
            elif field == "camera_name":
                val = val.strip() if isinstance(val, str) else val
                if not val or len(val) > 100:
                    return jsonify({"error": "Invalid camera name"}), 400
            elif field == "location":
                val = val.strip() if isinstance(val, str) else val
                if len(val) > 200:
                    return jsonify({"error": "Location too long"}), 400
            fields.append(f"{field} = %s")
            values.append(val)

    if not fields:
        return jsonify({"error": "No fields to update"}), 400

    values.append(camera_id)
    execute_update(f"UPDATE cameras SET {', '.join(fields)} WHERE id = %s", values)

    camera = execute_query("SELECT * FROM cameras WHERE id = %s", (camera_id,))
    security_logger.info(f"Camera updated: id={camera_id} by={request.user.get('username')}")
    return jsonify({"camera": camera[0]})


@cameras_bp.route("/<int:camera_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_camera(camera_id):
    cameras = execute_query("SELECT id FROM cameras WHERE id = %s", (camera_id,))
    if not cameras:
        return jsonify({"error": "Camera not found"}), 404

    execute_update("DELETE FROM cameras WHERE id = %s", (camera_id,))
    security_logger.info(f"Camera deleted: id={camera_id} by={request.user.get('username')}")
    return jsonify({"message": "Camera deleted"})


@cameras_bp.route("/<int:camera_id>/detect", methods=["POST"])
@token_required
@role_required("admin")
@limiter.limit(Config.RATE_LIMIT_DETECT)
def detect_camera(camera_id):
    cameras = execute_query("SELECT * FROM cameras WHERE id = %s", (camera_id,))
    if not cameras:
        return jsonify({"error": "Camera not found"}), 404

    camera = cameras[0]
    video_source = None

    data = request.get_json() or {}
    if "video_source" in data:
        video_source = data["video_source"]
        try:
            video_source = _validate_video_path(video_source)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    from backend.services.detection import run_detection
    import threading

    def run_in_thread():
        try:
            result = run_detection(
                camera_id=camera_id,
                video_source=video_source,
                speed_limit=float(camera["speed_limit"]),
                distance_meters=float(camera["measurement_distance"]),
            )
            app_logger = logging.getLogger("app")
            app_logger.info(f"Detection completed: {result}")
        except Exception as e:
            logging.getLogger("security").error(f"Detection error: {e}")
            from backend.services.detection import _run_status
            for rid in list(_run_status.keys()):
                if _run_status[rid].get("status") in ("loading", "processing"):
                    _run_status[rid]["status"] = "failed"
                    _run_status[rid]["error"] = str(e)

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()

    import time
    time.sleep(0.5)
    runs = execute_query(
        "SELECT id FROM detection_runs WHERE camera_id = %s ORDER BY id DESC LIMIT 1",
        (camera_id,),
    )
    latest_run_id = runs[0]["id"] if runs else None

    security_logger.info(f"Detection started: camera={camera_id} run={latest_run_id} by={request.user.get('username')}")
    return jsonify({"message": "Detection started", "camera_id": camera_id, "run_id": latest_run_id})


@cameras_bp.route("/detection-status/<int:run_id>", methods=["GET"])
@token_required
def detection_status(run_id):
    from backend.services.detection import get_run_status
    status = get_run_status(run_id)

    runs = execute_query("SELECT * FROM detection_runs WHERE id = %s", (run_id,))
    db_status = runs[0] if runs else {}

    speeds = status.get("speeds", [])
    speeds_this_run = speeds[-20:] if len(speeds) > 20 else speeds

    return jsonify({
        "run_id": run_id,
        "status": status.get("status", db_status.get("status", "unknown")),
        "frames": status.get("frames", 0),
        "vehicles": status.get("vehicles", 0),
        "violations": status.get("violations", 0),
        "speed_limit": status.get("speed_limit", 0),
        "speeds": speeds_this_run,
        "db_status": db_status.get("status"),
    })
