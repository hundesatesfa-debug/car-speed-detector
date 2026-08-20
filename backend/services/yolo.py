import hashlib
import logging
from ultralytics import YOLO
from backend.config import Config

security_logger = logging.getLogger("security")

_model = None


def get_model():
    global _model
    if _model is None:
        model_path = Config.MODEL_PATH
        security_logger.info(f"Loading YOLO model from {model_path}")

        if Config.MODEL_SHA256:
            h = hashlib.sha256()
            with open(model_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            actual_hash = h.hexdigest()
            if actual_hash != Config.MODEL_SHA256:
                security_logger.error(
                    f"YOLO model integrity check FAILED! Expected {Config.MODEL_SHA256[:16]}..., got {actual_hash[:16]}..."
                )
                raise RuntimeError("YOLO model integrity check failed - model may be tampered with")
            security_logger.info("YOLO model integrity verified")

        _model = YOLO(model_path)
        security_logger.info("YOLO model loaded successfully")
    return _model


def detect_and_track(frame, conf=None, classes=None):
    model = get_model()
    if conf is None:
        conf = Config.CONFIDENCE
    if classes is None:
        classes = Config.VEHICLE_CLASSES

    results = model.track(
        frame,
        persist=True,
        conf=conf,
        classes=classes,
        verbose=False,
    )
    return results[0]


def get_vehicle_class_name(class_id):
    model = get_model()
    return model.names.get(int(class_id), "unknown")


VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
