from flask import Blueprint, request, jsonify
from backend.routes.auth import token_required
from backend.database import execute_query

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("", methods=["GET"])
@token_required
def get_reports():
    total_violations = execute_query("SELECT COUNT(*) as count FROM violations")
    total_cameras = execute_query("SELECT COUNT(*) as count FROM cameras")
    active_cameras = execute_query("SELECT COUNT(*) as count FROM cameras WHERE status = 'active'")
    today_violations = execute_query(
        "SELECT COUNT(*) as count FROM violations WHERE DATE(violation_time) = CURDATE()"
    )
    highest_speed = execute_query("SELECT MAX(speed) as max_speed FROM violations")
    avg_speed = execute_query("SELECT AVG(speed) as avg_speed FROM violations")

    by_camera = execute_query(
        """SELECT c.camera_name as name, COUNT(v.id) as violation_count
           FROM cameras c
           LEFT JOIN violations v ON c.id = v.camera_id
           GROUP BY c.id, c.camera_name
           ORDER BY violation_count DESC"""
    )

    by_date = execute_query(
        """SELECT DATE(violation_time) as date, COUNT(*) as count
           FROM violations
           GROUP BY DATE(violation_time)
           ORDER BY date DESC
           LIMIT 30"""
    )

    by_vehicle_type = execute_query(
        """SELECT vt.vehicle_type, COUNT(*) as count
           FROM violations v
           LEFT JOIN vehicles vt ON v.vehicle_id = vt.id
           WHERE vt.vehicle_type IS NOT NULL
           GROUP BY vt.vehicle_type
           ORDER BY count DESC"""
    )

    top_plates = execute_query(
        """SELECT pl.plate_number, COUNT(*) as count, MAX(v.speed) as max_speed
           FROM violations v
           LEFT JOIN plates pl ON v.plate_id = pl.id
           WHERE pl.plate_number IS NOT NULL
           GROUP BY pl.plate_number
           ORDER BY count DESC
           LIMIT 10"""
    )

    recent = execute_query(
        """SELECT v.id, v.speed, v.speed_limit, v.violation_time, v.status, v.camera_id,
                  c.camera_name, pl.plate_number, vt.vehicle_type, vt.object_id
           FROM violations v
           LEFT JOIN cameras c ON v.camera_id = c.id
           LEFT JOIN vehicles vt ON v.vehicle_id = vt.id
           LEFT JOIN plates pl ON v.plate_id = pl.id
           ORDER BY v.violation_time DESC
           LIMIT 10"""
    )

    return jsonify({
        "summary": {
            "total_violations": total_violations[0]["count"] if total_violations else 0,
            "total_cameras": total_cameras[0]["count"] if total_cameras else 0,
            "active_cameras": active_cameras[0]["count"] if active_cameras else 0,
            "today_violations": today_violations[0]["count"] if today_violations else 0,
            "highest_speed": float(highest_speed[0]["max_speed"]) if highest_speed and highest_speed[0]["max_speed"] else 0,
            "average_speed": round(float(avg_speed[0]["avg_speed"]), 1) if avg_speed and avg_speed[0]["avg_speed"] else 0,
        },
        "by_camera": by_camera,
        "by_date": by_date,
        "by_vehicle_type": by_vehicle_type,
        "top_plates": top_plates,
        "recent_violations": recent,
    })
