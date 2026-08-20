import cv2
import os
import time
import logging
import threading
from datetime import datetime

from backend.config import Config

PROJECT_ROOT = Config.PROJECT_ROOT

security_logger = logging.getLogger("security")
app_logger = logging.getLogger("app")

from backend.services.yolo import detect_and_track
from backend.services.speed import (
    SpeedState,
    check_line_crossing,
    check_speed_line,
    mark_violation,
    is_violation_recorded,
)
from backend.services.plate import recognize_plate
from backend.database import execute_insert, execute_update
from backend.utils.helpers import generate_violation_filename, save_evidence_image, ensure_folder

VEHICLE_CLASSES_MAP = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

_run_status = {}
_run_ttl = {}
_stop_flags = {}


def get_run_status(run_id):
    return _run_status.get(run_id, {"status": "unknown"})


def request_stop(run_id):
    if run_id in _stop_flags:
        _stop_flags[run_id] = True
        security_logger.info(f"Stop requested for run {run_id}")
        return True
    return False


def _cleanup_old_runs():
    now = time.time()
    expired = [rid for rid, ts in _run_ttl.items() if now - ts > 7200]
    for rid in expired:
        _run_status.pop(rid, None)
        _run_ttl.pop(rid, None)
        _stop_flags.pop(rid, None)


def run_detection(camera_id, stream_source=None, speed_limit=50, distance_meters=10.0):
    _cleanup_old_runs()

    ensure_folder(Config.VIOLATIONS_FOLDER)

    source_display = stream_source or "default"
    run_id = execute_insert(
        "INSERT INTO detection_runs (camera_id, video_source, started_at, status) VALUES (%s, %s, NOW(), 'running')",
        (camera_id, source_display),
    )

    _stop_flags[run_id] = False
    _run_status[run_id] = {
        "status": "loading",
        "frames": 0,
        "vehicles": 0,
        "violations": 0,
        "speeds": [],
        "speed_limit": speed_limit,
        "run_id": run_id,
        "camera_id": camera_id,
    }
    _run_ttl[run_id] = time.time()

    try:
        cap = cv2.VideoCapture(stream_source)
        if not cap.isOpened():
            execute_update("UPDATE detection_runs SET status='failed' WHERE id=%s", (run_id,))
            _run_status[run_id]["status"] = "failed"
            _run_status[run_id]["error"] = "Could not open stream"
            security_logger.error(f"Detection run {run_id}: Could not open stream {stream_source}")
            return {"error": "Could not open stream", "run_id": run_id}

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0

        frame_number = 0
        vehicles_detected = 0
        violations_found = 0
        plate_cache = {}
        vehicle_db_ids = {}
        all_speeds = []
        line_a_y = 200
        line_b_y = 400
        consecutive_failures = 0
        max_failures = 60

        speed_state = SpeedState()

        _run_status[run_id]["status"] = "processing"
        security_logger.info(f"Detection run {run_id}: Stream opened, processing live feed")

        while not _stop_flags.get(run_id, False):
            success, frame = cap.read()
            if not success:
                consecutive_failures += 1
                if consecutive_failures > max_failures:
                    security_logger.warning(f"Detection run {run_id}: Too many consecutive read failures, stopping")
                    break
                time.sleep(0.1)
                continue

            consecutive_failures = 0
            frame_number += 1
            _run_status[run_id]["frames"] = frame_number

            result = detect_and_track(frame)

            if result.boxes is None or result.boxes.id is None:
                continue

            boxes = result.boxes.xyxy.cpu().numpy()
            ids = result.boxes.id.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy()

            for box, object_id, class_id in zip(boxes, ids, classes):
                object_id = int(object_id)
                class_id = int(class_id)

                if class_id not in VEHICLE_CLASSES_MAP:
                    continue

                vehicle_type = VEHICLE_CLASSES_MAP[class_id]
                vehicles_detected += 1
                _run_status[run_id]["vehicles"] = vehicles_detected

                x1, y1, x2, y2 = map(int, box)
                x1, y1 = max(0, x1), max(0, y1)
                x2 = min(frame.shape[1], x2)
                y2 = min(frame.shape[0], y2)

                if x2 <= x1 or y2 <= y1:
                    continue

                center_y = (y1 + y2) // 2

                check_line_crossing(speed_state, object_id, center_y, line_a_y, frame_number)
                speed = check_speed_line(speed_state, object_id, center_y, line_b_y, frame_number, fps, distance_meters)

                if speed is not None:
                    speed_entry = {
                        "object_id": object_id,
                        "vehicle_type": vehicle_type,
                        "speed": round(speed, 2),
                    }
                    all_speeds.append(speed_entry)
                    _run_status[run_id]["speeds"] = list(all_speeds[-50:])

                    if object_id not in vehicle_db_ids:
                        vehicle_db_id = execute_insert(
                            """INSERT INTO vehicles (detection_run_id, object_id, vehicle_type, first_seen, last_seen)
                               VALUES (%s, %s, %s, NOW(), NOW())""",
                            (run_id, object_id, vehicle_type),
                        )
                        vehicle_db_ids[object_id] = vehicle_db_id

                    if speed > speed_limit and not is_violation_recorded(speed_state, object_id):
                        vehicle_db_id = vehicle_db_ids[object_id]

                        plate_text = None
                        plate_db_id = None
                        if object_id not in plate_cache:
                            vehicle_crop = frame[y1:y2, x1:x2]
                            if vehicle_crop.size > 0:
                                plate_text, conf, plate_img = recognize_plate(vehicle_crop)
                                if plate_text:
                                    plate_cache[object_id] = (plate_text, conf)
                                    plate_db_id = execute_insert(
                                        """INSERT INTO plates (vehicle_id, plate_number, confidence, detected_at)
                                           VALUES (%s, %s, %s, NOW())""",
                                        (vehicle_db_id, plate_text, round(conf, 2)),
                                    )
                        else:
                            plate_text, _ = plate_cache[object_id]

                        filename = generate_violation_filename(object_id)
                        image_path = os.path.join(Config.VIOLATIONS_FOLDER, filename)

                        annotations = [
                            {"text": f"ID: {object_id} | {vehicle_type}", "position": (x1, max(25, y1 - 10)), "color": (0, 255, 0)},
                            {"text": f"Speed: {speed:.1f} km/h", "position": (x1, min(frame.shape[0] - 50, y2 + 25)), "color": (0, 0, 255), "thickness": 2},
                            {"text": f"Limit: {speed_limit} km/h", "position": (x1, min(frame.shape[0] - 20, y2 + 55)), "color": (255, 255, 0)},
                            {"text": "VIOLATION", "position": (10, 30), "color": (0, 0, 255), "scale": 1.0, "thickness": 3},
                        ]
                        if plate_text:
                            annotations.append({"text": f"Plate: {plate_text}", "position": (x1, min(frame.shape[0] - 80, y2 + 85)), "color": (0, 255, 255)})

                        save_evidence_image(frame, image_path, annotations)

                        execute_insert(
                            """INSERT INTO violations
                               (camera_id, detection_run_id, vehicle_id, plate_id, speed, speed_limit, evidence_path, violation_time, status)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 'pending')""",
                            (camera_id, run_id, vehicle_db_id, plate_db_id,
                             round(speed, 2), speed_limit, image_path),
                        )

                        mark_violation(speed_state, object_id)
                        violations_found += 1
                        _run_status[run_id]["violations"] = violations_found
                        security_logger.info(
                            f"Violation: run={run_id} vehicle={vehicle_type} id={object_id} speed={speed:.1f} plate={plate_text}"
                        )

        cap.release()

        was_stopped = _stop_flags.get(run_id, False)
        final_status = "stopped" if was_stopped else "completed"

        execute_update(
            "UPDATE detection_runs SET status=%s, ended_at=NOW() WHERE id=%s",
            (final_status, run_id),
        )

        _run_status[run_id]["status"] = final_status
        _run_status[run_id]["violations"] = violations_found
        _stop_flags.pop(run_id, None)

        result = {
            "run_id": run_id,
            "frames": frame_number,
            "vehicles": vehicles_detected,
            "violations": violations_found,
            "speeds_detected": all_speeds,
            "speed_limit": speed_limit,
            "status": final_status,
        }
        app_logger.info(
            f"Detection {final_status}: run={run_id} frames={frame_number} vehicles={vehicles_detected} violations={violations_found} speeds={len(all_speeds)}"
        )
        return result

    except Exception as e:
        security_logger.error(f"Detection error: run={run_id} error={e}")
        execute_update("UPDATE detection_runs SET status='failed' WHERE id=%s", (run_id,))
        _run_status[run_id]["status"] = "failed"
        _run_status[run_id]["error"] = str(e)
        _stop_flags.pop(run_id, None)
        return {"error": str(e), "run_id": run_id}
