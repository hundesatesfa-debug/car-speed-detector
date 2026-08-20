import cv2 as cv
import easyocr
from ultralytics import YOLO
import os
import re


# ==========================================
# SETTINGS
# ==========================================

VIDEO_PATH = "trash.mp4"
MODEL_PATH = "yolo11n.pt"

CONFIDENCE = 0.35

DEBUG_FOLDER = "plate_debug"

os.makedirs(DEBUG_FOLDER, exist_ok=True)


# ==========================================
# VEHICLE CLASSES
# ==========================================

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}


# ==========================================
# LOAD MODELS
# ==========================================

print("Loading YOLO...")
model = YOLO(MODEL_PATH)

print("Loading EasyOCR...")
reader = easyocr.Reader(
    ["en"],
    gpu=False
)

print("✅ Models loaded")


# ==========================================
# OPEN VIDEO
# ==========================================

video = cv.VideoCapture(VIDEO_PATH)

if not video.isOpened():
    print("❌ Could not open video.")
    exit()

print("✅ Video opened")


# ==========================================
# VARIABLES
# ==========================================

frame_number = 0

processed_ids = set()


# ==========================================
# OCR FUNCTION
# ==========================================

def read_plate(plate_image):

    if plate_image is None or plate_image.size == 0:
        return []


    # --------------------------------------
    # Resize
    # --------------------------------------

    enlarged = cv.resize(
        plate_image,
        None,
        fx=5,
        fy=5,
        interpolation=cv.INTER_CUBIC
    )


    # --------------------------------------
    # Grayscale
    # --------------------------------------

    gray = cv.cvtColor(
        enlarged,
        cv.COLOR_BGR2GRAY
    )


    # --------------------------------------
    # Create several versions
    # --------------------------------------

    versions = []

    versions.append(
        ("original", enlarged)
    )

    versions.append(
        ("gray", gray)
    )


    # Contrast enhancement

    equalized = cv.equalizeHist(gray)

    versions.append(
        ("equalized", equalized)
    )


    # Gaussian threshold

    threshold = cv.adaptiveThreshold(
        gray,
        255,
        cv.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv.THRESH_BINARY,
        31,
        11
    )

    versions.append(
        ("threshold", threshold)
    )


    # Otsu threshold

    _, otsu = cv.threshold(
        gray,
        0,
        255,
        cv.THRESH_BINARY + cv.THRESH_OTSU
    )

    versions.append(
        ("otsu", otsu)
    )


    # --------------------------------------
    # OCR
    # --------------------------------------

    all_results = []


    for name, image in versions:

        results = reader.readtext(
            image,
            detail=1,
            paragraph=False,
            allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )


        for detection in results:

            bbox, text, confidence = detection

            text = text.upper()

            # Remove spaces and symbols
            text = re.sub(
                r"[^A-Z0-9]",
                "",
                text
            )


            if len(text) < 3:
                continue


            all_results.append(
                (
                    text,
                    confidence,
                    name
                )
            )


    return all_results


# ==========================================
# FIND PLATE CANDIDATES
# ==========================================

def find_plate_candidates(vehicle):

    candidates = []


    if vehicle is None or vehicle.size == 0:
        return candidates


    height, width = vehicle.shape[:2]


    # --------------------------------------
    # Focus mainly on lower half
    # --------------------------------------

    lower = vehicle[
        int(height * 0.40):height,
        0:width
    ]


    if lower.size == 0:
        return candidates


    gray = cv.cvtColor(
        lower,
        cv.COLOR_BGR2GRAY
    )


    # --------------------------------------
    # Blur slightly
    # --------------------------------------

    blurred = cv.GaussianBlur(
        gray,
        (5, 5),
        0
    )


    # --------------------------------------
    # Edge detection
    # --------------------------------------

    edges = cv.Canny(
        blurred,
        50,
        150
    )


    # --------------------------------------
    # Find contours
    # --------------------------------------

    contours, _ = cv.findContours(
        edges,
        cv.RETR_LIST,
        cv.CHAIN_APPROX_SIMPLE
    )


    for contour in contours:

        area = cv.contourArea(contour)

        if area < 80:
            continue


        x, y, w, h = cv.boundingRect(
            contour
        )


        if h == 0:
            continue


        aspect_ratio = w / h


        # License plates are generally
        # wider than they are tall.

        if (
            1.5 <= aspect_ratio <= 6.5
            and w >= 25
            and h >= 8
        ):

            # Add some padding

            padding_x = int(w * 0.10)
            padding_y = int(h * 0.20)


            x1 = max(
                0,
                x - padding_x
            )

            y1 = max(
                0,
                y - padding_y
            )

            x2 = min(
                lower.shape[1],
                x + w + padding_x
            )

            y2 = min(
                lower.shape[0],
                y + h + padding_y
            )


            candidate = lower[
                y1:y2,
                x1:x2
            ]


            if candidate.size != 0:

                candidates.append(
                    candidate
                )


    return candidates


# ==========================================
# MAIN LOOP
# ==========================================

while True:

    success, frame = video.read()

    if not success:
        break


    frame_number += 1


    # ======================================
    # YOLO TRACKING
    # ======================================

    results = model.track(
        frame,
        persist=True,
        conf=CONFIDENCE,
        verbose=False
    )

    result = results[0]


    if (
        result.boxes is None
        or result.boxes.id is None
    ):

        cv.imshow(
            "License Plate Recognition",
            frame
        )

        if cv.waitKey(1) & 0xFF == ord("q"):
            break

        continue


    boxes = result.boxes.xyxy.cpu().numpy()
    ids = result.boxes.id.cpu().numpy()
    classes = result.boxes.cls.cpu().numpy()


    # ======================================
    # PROCESS VEHICLES
    # ======================================

    for box, object_id, class_id in zip(
        boxes,
        ids,
        classes
    ):

        class_id = int(class_id)
        object_id = int(object_id)


        if class_id not in VEHICLE_CLASSES:
            continue


        vehicle_type = VEHICLE_CLASSES[class_id]


        x1, y1, x2, y2 = map(
            int,
            box
        )


        # Keep coordinates inside frame

        x1 = max(0, x1)
        y1 = max(0, y1)

        x2 = min(
            frame.shape[1],
            x2
        )

        y2 = min(
            frame.shape[0],
            y2
        )


        if x2 <= x1 or y2 <= y1:
            continue


        # ==================================
        # DRAW VEHICLE
        # ==================================

        cv.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2
        )


        cv.putText(
            frame,
            f"{vehicle_type} ID:{object_id}",
            (x1, max(25, y1 - 10)),
            cv.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )


        # ==================================
        # VEHICLE CROP
        # ==================================

        vehicle = frame[
            y1:y2,
            x1:x2
        ]


        if vehicle.size == 0:
            continue


        # ==================================
        # SAVE VEHICLE CROP ONCE
        # ==================================

        if object_id not in processed_ids:

            vehicle_path = os.path.join(
                DEBUG_FOLDER,
                f"vehicle_{object_id}_{vehicle_type}.jpg"
            )

            cv.imwrite(
                vehicle_path,
                vehicle
            )

            print(
                f"📸 Saved vehicle: {vehicle_path}"
            )


        # ==================================
        # FIND PLATE CANDIDATES
        # ==================================

        candidates = find_plate_candidates(
            vehicle
        )


        if not candidates:

            if object_id not in processed_ids:

                print(
                    f"⚠️ ID {object_id}: "
                    f"No plate candidate found"
                )

            continue


        # ==================================
        # TEST PLATE CANDIDATES
        # ==================================

        best_text = None
        best_confidence = 0
        best_image = None


        for index, candidate in enumerate(
            candidates
        ):

            # Save candidate

            candidate_path = os.path.join(
                DEBUG_FOLDER,
                f"plate_{object_id}_{index}.jpg"
            )

            if object_id not in processed_ids:

                cv.imwrite(
                    candidate_path,
                    candidate
                )


            # OCR

            ocr_results = read_plate(
                candidate
            )


            for text, confidence, method in ocr_results:

                print(
                    f"🔎 ID {object_id} "
                    f"candidate {index} "
                    f"→ {text} "
                    f"({confidence:.2f}) "
                    f"[{method}]"
                )


                if confidence > best_confidence:

                    best_text = text
                    best_confidence = confidence
                    best_image = candidate


        # ==================================
        # FINAL PLATE RESULT
        # ==================================

        if best_text is not None:

            print(
                f"🚘 ID {object_id} "
                f"({vehicle_type}) "
                f"→ PLATE: {best_text} "
                f"| Confidence: "
                f"{best_confidence:.2f}"
            )


            cv.putText(
                frame,
                f"PLATE: {best_text}",
                (
                    x1,
                    min(
                        frame.shape[0] - 15,
                        y2 + 30
                    )
                ),
                cv.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2
            )


            # Save best plate

            if object_id not in processed_ids:

                best_path = os.path.join(
                    DEBUG_FOLDER,
                    f"BEST_PLATE_{object_id}.jpg"
                )

                cv.imwrite(
                    best_path,
                    best_image
                )

                print(
                    f"✅ Best plate saved: "
                    f"{best_path}"
                )


        else:

            print(
                f"❌ ID {object_id}: "
                f"Plate could not be read"
            )


        processed_ids.add(
            object_id
        )


    # ======================================
    # DISPLAY
    # ======================================

    cv.imshow(
        "License Plate Recognition",
        frame
    )


    # ======================================
    # QUIT
    # ======================================

    if cv.waitKey(1) & 0xFF == ord("q"):
        break


# ==========================================
# CLEANUP
# ==========================================

video.release()

cv.destroyAllWindows()

print()
print("==========================================")
print("Program finished.")
print("==========================================")
print(
    f"🔎 Check '{DEBUG_FOLDER}' "
    f"for saved plate candidates."
)