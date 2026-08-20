import os
import logging
from flask import Blueprint, request, jsonify, send_file
from backend.routes.auth import token_required
from backend.database import execute_query
from backend.config import Config

security_logger = logging.getLogger("security")

violations_bp = Blueprint("violations", __name__)


@violations_bp.route("", methods=["GET"])
@token_required
def list_violations():
    camera_id = request.args.get("camera_id")
    plate = request.args.get("plate")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    status = request.args.get("status")

    query = """
        SELECT v.*, c.camera_name, c.location as camera_location,
               pl.plate_number, vt.vehicle_type, vt.object_id
        FROM violations v
        LEFT JOIN cameras c ON v.camera_id = c.id
        LEFT JOIN vehicles vt ON v.vehicle_id = vt.id
        LEFT JOIN plates pl ON v.plate_id = pl.id
        WHERE 1=1
    """
    params = []

    if camera_id:
        try:
            camera_id = int(camera_id)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid camera_id"}), 400
        query += " AND v.camera_id = %s"
        params.append(camera_id)
    if plate:
        if len(plate) > 20:
            return jsonify({"error": "Plate search too long"}), 400
        query += " AND pl.plate_number LIKE %s"
        params.append(f"%{plate}%")
    if date_from:
        query += " AND v.violation_time >= %s"
        params.append(date_from)
    if date_to:
        query += " AND v.violation_time <= %s"
        params.append(date_to)
    if status:
        if status not in ("pending", "confirmed", "dismissed", "processed"):
            return jsonify({"error": "Invalid status"}), 400
        query += " AND v.status = %s"
        params.append(status)

    query += " ORDER BY v.violation_time DESC"

    violations = execute_query(query, params)
    return jsonify({"violations": violations, "count": len(violations)})


@violations_bp.route("/<int:violation_id>", methods=["GET"])
@token_required
def get_violation(violation_id):
    violations = execute_query(
        """SELECT v.*, c.camera_name, c.location as camera_location,
                  pl.plate_number, vt.vehicle_type, vt.object_id
           FROM violations v
           LEFT JOIN cameras c ON v.camera_id = c.id
           LEFT JOIN vehicles vt ON v.vehicle_id = vt.id
           LEFT JOIN plates pl ON v.plate_id = pl.id
           WHERE v.id = %s""",
        (violation_id,),
    )
    if not violations:
        return jsonify({"error": "Violation not found"}), 404
    return jsonify({"violation": violations[0]})


@violations_bp.route("/<int:violation_id>/image", methods=["GET"])
@token_required
def get_violation_image(violation_id):
    violations = execute_query("SELECT evidence_path FROM violations WHERE id = %s", (violation_id,))
    if not violations or not violations[0]["evidence_path"]:
        return jsonify({"error": "No evidence image"}), 404

    image_path = violations[0]["evidence_path"]

    violations_folder = os.path.realpath(Config.VIOLATIONS_FOLDER)
    real_path = os.path.realpath(image_path)

    if not real_path.startswith(violations_folder):
        security_logger.warning(f"Path traversal attempt on evidence: id={violation_id} path={image_path} user={request.user.get('username')}")
        return jsonify({"error": "Access denied"}), 403

    if not os.path.exists(real_path):
        return jsonify({"error": "Image file not found"}), 404

    return send_file(real_path, mimetype="image/jpeg")


@violations_bp.route("/<int:violation_id>", methods=["PUT"])
@token_required
def update_violation(violation_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    violations = execute_query("SELECT id FROM violations WHERE id = %s", (violation_id,))
    if not violations:
        return jsonify({"error": "Violation not found"}), 404

    new_status = data.get("status")
    if new_status:
        if new_status not in ("pending", "confirmed", "dismissed", "processed"):
            return jsonify({"error": "Invalid status"}), 400
        execute_query(
            "UPDATE violations SET status = %s WHERE id = %s",
            (new_status, violation_id),
            fetch=False,
        )
        security_logger.info(f"Violation {violation_id} status changed to {new_status} by {request.user.get('username')}")

    return jsonify({"message": "Updated"})
