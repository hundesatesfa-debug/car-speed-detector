import os
import cv2
import numpy as np
from datetime import datetime


def ensure_folder(path):
    os.makedirs(path, exist_ok=True)


def generate_violation_filename(object_id):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"violation_{object_id}_{timestamp}.jpg"


def save_evidence_image(frame, output_path, annotations=None):
    img = frame.copy()
    if annotations:
        for ann in annotations:
            text = ann.get("text", "")
            pos = ann.get("position", (10, 30))
            color = ann.get("color", (0, 255, 0))
            scale = ann.get("scale", 0.7)
            thickness = ann.get("thickness", 2)
            cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)

    cv2.imwrite(output_path, img)
    return output_path
