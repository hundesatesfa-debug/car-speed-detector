from ultralytics import YOLO
import cv2 as cv
import os
import pymysql
from datetime import datetime


# ============================================================
# SETTINGS
# ============================================================

VIDEO_PATH = "trash.mp4"
MODEL_PATH = "yolo11n.pt"

DISTANCE_METERS = 10
SPEED_LIMIT = 10

LINE_A = 200
LINE_B = 400

VIOLATION_FOLDER = "violations"

VEHICLE_CLASSES = [2, 3, 5, 7]


# ============================================================
# CREATE VIOLATION FOLDER
# ============================================================

os.makedirs(VIOLATION_FOLDER, exist_ok=True)


# ============================================================
# MYSQL CONNECTION
# ============================================================

try:

    connection = pymysql.connect(
        host="localhost",
        user="root",
        password="126578",
        database="speed_detection"
    )

    cursor = connection.cursor()

    print("✅ Connected to MySQL!")

except pymysql.Error as error:

    print("❌ MySQL connection failed:")
    print(error)

    connection = None
    cursor = None


# ============================================================
# LOAD YOLO
# ============================================================

model = YOLO(MODEL_PATH)


# ============================================================
# OPEN VIDEO
# ============================================================

video = cv.VideoCapture(VIDEO_PATH)

if not video.isOpened():

    print("❌ Could not open video.")

    if connection:
        connection.close()

    exit()


# ============================================================
# FPS
# ============================================================

fps = video.get(cv.CAP_PROP_FPS)

print(f"Video FPS: {fps}")

if fps <= 0:

    print("❌ Could not determine video FPS.")

    video.release()

    if connection:
        connection.close()

    exit()


# ============================================================
# VARIABLES
# ============================================================

frame_number = 0

start_frames = {}

speeds = {}

violations = set()


# ============================================================
# MAIN LOOP
# ============================================================

while True:

    isTrue, frame = video.read()

    if not isTrue:
        break

    frame_number += 1


    # ========================================================
    # YOLO TRACKING
    # ========================================================

    results = model.track(
        frame,
        persist=True,
        conf=0.3,
        classes=VEHICLE_CLASSES,
        verbose=False
    )

    result = results[0]


    # ========================================================
    # PROCESS OBJECTS
    # ========================================================

    if (
        result.boxes is not None
        and result.boxes.id is not None
    ):

        boxes = result.boxes.xyxy.cpu().numpy()

        ids = result.boxes.id.cpu().numpy()

        classes = result.boxes.cls.cpu().numpy()


        for box, object_id, class_id in zip(
            boxes,
            ids,
            classes
        ):

            x1, y1, x2, y2 = box

            object_id = int(object_id)

            class_id = int(class_id)


            # =================================================
            # VEHICLE TYPE
            # =================================================

            vehicle_type = model.names[class_id]


            # =================================================
            # CENTER
            # =================================================

            center_x = int((x1 + x2) / 2)

            center_y = int((y1 + y2) / 2)


            # =================================================
            # LINE A
            # =================================================

            if (
                center_y >= LINE_A
                and object_id not in start_frames
            ):

                start_frames[object_id] = frame_number

                print(
                    f"🚗 {vehicle_type} "
                    f"Object {object_id} "
                    f"crossed Line A "
                    f"at frame {frame_number}"
                )


            # =================================================
            # LINE B
            # =================================================

            if (
                center_y >= LINE_B
                and object_id in start_frames
                and object_id not in speeds
            ):

                start_frame = start_frames[object_id]

                frames_taken = (
                    frame_number - start_frame
                )

                time_seconds = (
                    frames_taken / fps
                )


                if time_seconds > 0:

                    # =========================================
                    # SPEED
                    # =========================================

                    speed_mps = (
                        DISTANCE_METERS /
                        time_seconds
                    )

                    speed_kmh = (
                        speed_mps * 3.6
                    )


                    speeds[object_id] = speed_kmh


                    print(
                        f"🚗 {vehicle_type} "
                        f"Object {object_id} "
                        f"speed: "
                        f"{speed_kmh:.2f} km/h"
                    )


                    # =========================================
                    # SPEED LIMIT
                    # =========================================

                    if (
                        speed_kmh > SPEED_LIMIT
                        and object_id not in violations
                    ):

                        print(
                            f"🚨 VIOLATION!"
                        )


                        # =====================================
                        # SAVE IMAGE
                        # =====================================

                        timestamp = datetime.now().strftime(
                            "%Y%m%d_%H%M%S"
                        )


                        filename = (
                            f"violation_"
                            f"{object_id}_"
                            f"{timestamp}.jpg"
                        )


                        image_path = os.path.join(
                            VIOLATION_FOLDER,
                            filename
                        )


                        cv.imwrite(
                            image_path,
                            frame
                        )


                        print(
                            f"📸 Evidence saved: "
                            f"{image_path}"
                        )


                        # =====================================
                        # SAVE MYSQL
                        # =====================================

                        if connection and cursor:

                            try:

                                sql = """
                                INSERT INTO violations
                                (
                                    object_id,
                                    vehicle_type,
                                    plate_number,
                                    speed,
                                    speed_limit,
                                    image_path,
                                    violation_time
                                )
                                VALUES
                                (%s, %s, %s, %s, %s, %s, %s)
                                """


                                cursor.execute(
                                    sql,
                                    (
                                        object_id,
                                        vehicle_type,
                                        None,
                                        speed_kmh,
                                        SPEED_LIMIT,
                                        image_path,
                                        datetime.now()
                                    )
                                )


                                connection.commit()


                                print(
                                    "🐬 Violation saved to MySQL!"
                                )


                            except pymysql.Error as error:

                                print(
                                    "❌ MySQL insert failed:"
                                )

                                print(error)


                        violations.add(object_id)


    # ========================================================
    # DRAW OBJECTS
    # ========================================================

    if (
        result.boxes is not None
        and result.boxes.id is not None
    ):

        boxes = result.boxes.xyxy.cpu().numpy()

        ids = result.boxes.id.cpu().numpy()

        classes = result.boxes.cls.cpu().numpy()


        for box, object_id, class_id in zip(
            boxes,
            ids,
            classes
        ):

            x1, y1, x2, y2 = box

            object_id = int(object_id)

            class_id = int(class_id)

            vehicle_type = model.names[class_id]


            center_x = int((x1 + x2) / 2)

            center_y = int((y1 + y2) / 2)


            # Bounding box

            cv.rectangle(
                frame,
                (int(x1), int(y1)),
                (int(x2), int(y2)),
                (0, 255, 0),
                2
            )


            # Center

            cv.circle(
                frame,
                (center_x, center_y),
                5,
                (0, 0, 255),
                -1
            )


            # Label

            label = (
                f"{vehicle_type} "
                f"ID:{object_id}"
            )


            cv.putText(
                frame,
                label,
                (
                    int(x1),
                    int(y1) - 10
                ),
                cv.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )


            # Speed

            if object_id in speeds:

                speed_text = (
                    f"{speeds[object_id]:.1f} km/h"
                )


                cv.putText(
                    frame,
                    speed_text,
                    (
                        int(x1),
                        int(y2) + 25
                    ),
                    cv.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2
                )


    # ========================================================
    # LINE A
    # ========================================================

    cv.line(
        frame,
        (0, LINE_A),
        (frame.shape[1], LINE_A),
        (255, 0, 0),
        2
    )


    cv.putText(
        frame,
        "LINE A",
        (20, LINE_A - 10),
        cv.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 0, 0),
        2
    )


    # ========================================================
    # LINE B
    # ========================================================

    cv.line(
        frame,
        (0, LINE_B),
        (frame.shape[1], LINE_B),
        (255, 0, 0),
        2
    )


    cv.putText(
        frame,
        "LINE B",
        (20, LINE_B - 10),
        cv.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 0, 0),
        2
    )


    # ========================================================
    # SPEED LIMIT
    # ========================================================

    cv.putText(
        frame,
        f"Speed Limit: {SPEED_LIMIT} km/h",
        (20, 40),
        cv.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )


    # ========================================================
    # DISPLAY
    # ========================================================

    cv.imshow(
        "Speed Detection",
        frame
    )


    # ========================================================
    # QUIT
    # ========================================================

    if cv.waitKey(20) & 0xFF == ord("q"):
        break


# ============================================================
# CLEAN UP
# ============================================================

video.release()

cv.destroyAllWindows()


if connection:

    cursor.close()

    connection.close()

    print("🐬 MySQL connection closed.")


print("Program finished.")