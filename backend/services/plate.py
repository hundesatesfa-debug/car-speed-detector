import cv2
import easyocr
import re

_reader = None


def get_reader():
    global _reader
    if _reader is None:
        print("[Plate] Loading EasyOCR...")
        _reader = easyocr.Reader(["en"], gpu=False)
        print("[Plate] EasyOCR loaded")
    return _reader


def read_plate(plate_image):
    if plate_image is None or plate_image.size == 0:
        return []

    enlarged = cv2.resize(plate_image, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)

    versions = []
    versions.append(("original", enlarged))
    versions.append(("gray", gray))

    equalized = cv2.equalizeHist(gray)
    versions.append(("equalized", equalized))

    threshold = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
    versions.append(("threshold", threshold))

    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    versions.append(("otsu", otsu))

    reader = get_reader()
    all_results = []

    for name, image in versions:
        results = reader.readtext(
            image,
            detail=1,
            paragraph=False,
            allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        )

        for detection in results:
            bbox, text, confidence = detection
            text = text.upper()
            text = re.sub(r"[^A-Z0-9]", "", text)

            if len(text) < 3:
                continue

            all_results.append((text, confidence, name))

    return all_results


def find_plate_candidates(vehicle):
    candidates = []
    if vehicle is None or vehicle.size == 0:
        return candidates

    height, width = vehicle.shape[:2]
    lower = vehicle[int(height * 0.40):height, 0:width]

    if lower.size == 0:
        return candidates

    gray = cv2.cvtColor(lower, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 80:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        if h == 0:
            continue

        aspect_ratio = w / h
        if 1.5 <= aspect_ratio <= 6.5 and w >= 25 and h >= 8:
            padding_x = int(w * 0.10)
            padding_y = int(h * 0.20)

            x1 = max(0, x - padding_x)
            y1 = max(0, y - padding_y)
            x2 = min(lower.shape[1], x + w + padding_x)
            y2 = min(lower.shape[0], y + h + padding_y)

            candidate = lower[y1:y2, x1:x2]
            if candidate.size != 0:
                candidates.append(candidate)

    return candidates


def recognize_plate(vehicle_crop):
    candidates = find_plate_candidates(vehicle_crop)
    if not candidates:
        return None, 0.0, None

    best_text = None
    best_confidence = 0.0
    best_image = None

    for candidate in candidates:
        ocr_results = read_plate(candidate)
        for text, confidence, method in ocr_results:
            if confidence > best_confidence:
                best_text = text
                best_confidence = confidence
                best_image = candidate

    return best_text, best_confidence, best_image
