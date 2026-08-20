# import cv2 as cv
#
# # 1. Load and resize the image ONCE
# img = cv.imread("pig.png")
#
#
# def rescaleFrame(frame, scale=0.75):
#     width = int(frame.shape[1] * scale)
#     height = int(frame.shape[0] * scale)
#     dim = (width, height)
#     return cv.resize(frame, dim, interpolation=cv.INTER_AREA)
#
#
# resized_img = rescaleFrame(img, scale=0.5)
#
# # 2. Open the video stream
# capture = cv.VideoCapture('trash.mp4')  # Replace with your video path or 0 for webcam
#
# # 3. Main loop to process and show video frames
# while True:
#     isTrue, frame = capture.read()
#
#     # Break loop if video finishes or fails to load
#     if not isTrue:
#         break
#
#     resized_frame = rescaleFrame(frame, scale=0.5)
#
#     # Display both windows continuously in the loop
#     cv.imshow("Resized Image", resized_img)
#     cv.imshow("Resized Video", resized_frame)
#
#     # cv.waitKey(20) waits 20ms per frame. Press 'd' to quit.
#     if cv.waitKey(20) & 0xFF == ord('d'):
#         break
#
# capture.release()
# cv.destroyAllWindows()
import cv2 as cv

img = cv.imread("pig.png")

# 1. BGR to Grayscale
gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

# 2. BGR to HSV
hsv = cv.cvtColor(img, cv.COLOR_BGR2HSV)

# 3. BGR to LAB
# lab = cv.cvtColor(img, cv.COLOR_BGR2LAB)
#
# # Display the converted images
# cv.imshow("Grayscale", gray)
# cv.imshow("HSV Space", hsv)
#
# cv.waitKey(0)
# cv.destroyAllWindows()