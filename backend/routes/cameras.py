import os
import re
import logging
import time
import threading
from flask import Blueprint, request, jsonify
from backend.routes.auth import token_required, role_required
from backend.database import execute_query, execute_insert, execute_update
from backend.config import Config
from backend.app import limiter

security_logger = logging.getLogger("security")

cameras_bp = Blueprint("cameras", __name__)


def _validate_stream_source(stream_source):
    if not stream_source or not stream_source.strip():
        return ""
    s = stream_source.strip()
    if s.isdigit():
        return s
    if s.startswith("rtsp://") or s.startswith("rtmp://") or s.startswith("http://") or s.startswith("https://"):
        return s
    if os.path.splitext(s)[1].lower() in (".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"):
        return s
    raise ValueError(
        "Invalid stream source. Use: 0 for webcam, RTSP/HTTP URL, or video file path"
    )


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

    stream_source = ""
    if "stream_source" in data and data["stream_source"].strip():
        try:
            stream_source = _validate_stream_source(data["stream_source"])
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    import secrets as _secrets
    camera_code = data.get("camera_code", f"CAM-{_secrets.token_hex(3).upper()}")

    camera_id = execute_insert(
        """INSERT INTO cameras
           (camera_code, camera_name, location, speed_limit, measurement_distance, camera_token_hash, stream_source, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (camera_code, name, location, speed_limit, distance, "", stream_source, "active"),
    )

    camera = execute_query("SELECT * FROM cameras WHERE id = %s", (camera_id,))
    security_logger.info(f"Camera created: id={camera_id} name={name} stream={stream_source} by={request.user.get('username')}")
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

    allowed_fields = ["camera_name", "location", "speed_limit", "measurement_distance", "status", "stream_source"]
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
            elif field == "stream_source":
                val = val.strip() if isinstance(val, str) else val
                if val:
                    try:
                        val = _validate_stream_source(val)
                    except ValueError as e:
                        return jsonify({"error": str(e)}), 400
                else:
                    val = ""
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

    existing_runs = execute_query(
        "SELECT id FROM detection_runs WHERE camera_id = %s AND status = 'running'",
        (camera_id,),
    )
    if existing_runs:
        return jsonify({"error": "Detection already running for this camera", "run_id": existing_runs[0]["id"]}), 409

    stream_source = camera.get("stream_source", "") or ""

    if not stream_source:
        return jsonify({"error": "No stream source configured. Edit this camera and set a stream source (e.g. 0 for webcam, or an RTSP/HTTP URL)."}), 400

    from backend.services.detection import run_detection

    def run_in_thread():
        try:
            result = run_detection(
                camera_id=camera_id,
                stream_source=stream_source,
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

    time.sleep(0.5)
    runs = execute_query(
        "SELECT id FROM detection_runs WHERE camera_id = %s ORDER BY id DESC LIMIT 1",
        (camera_id,),
    )
    latest_run_id = runs[0]["id"] if runs else None

    security_logger.info(f"Detection started: camera={camera_id} stream={stream_source} run={latest_run_id} by={request.user.get('username')}")
    return jsonify({"message": "Detection started", "camera_id": camera_id, "run_id": latest_run_id})


@cameras_bp.route("/<int:camera_id>/stop", methods=["POST"])
@token_required
@role_required("admin")
def stop_detection(camera_id):
    cameras = execute_query("SELECT id FROM cameras WHERE id = %s", (camera_id,))
    if not cameras:
        return jsonify({"error": "Camera not found"}), 404

    running = execute_query(
        "SELECT id FROM detection_runs WHERE camera_id = %s AND status = 'running' ORDER BY id DESC LIMIT 1",
        (camera_id,),
    )
    if not running:
        return jsonify({"error": "No active detection running for this camera"}), 404

    run_id = running[0]["id"]
    from backend.services.detection import request_stop
    stopped = request_stop(run_id)

    if stopped:
        security_logger.info(f"Detection stop requested: camera={camera_id} run={run_id} by={request.user.get('username')}")
        return jsonify({"message": "Stop requested", "run_id": run_id})
    else:
        return jsonify({"error": "Could not stop detection"}), 400


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
