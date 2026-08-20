from ultralytics import YOLO
import cv2 as cv

model = YOLO("yolo11n.pt")

video = cv.VideoCapture("trash.mp4")

while True:
    isTrue, frame = video.read()

    if not isTrue:
        break

    # Detect + track objects
    results = model.track(frame, persist=True)

    # Draw tracking information
    annotated_frame = results[0].plot()

    cv.imshow("Tracking", annotated_frame)

    if cv.waitKey(20) & 0xFF == ord("q"):
        break

video.release()
cv.destroyAllWindows()