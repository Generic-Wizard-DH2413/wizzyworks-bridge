import cv2
import numpy as np

# Initialize webcam
cap = cv2.VideoCapture(0)

# Set high resolution for better marker detection
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

# Set exposure for bright phone screen in dark room
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # 0.25 = manual mode
# Typical value for a bright object in a dark room (may need adjustment)
cap.set(cv2.CAP_PROP_EXPOSURE, -6)

# Use a standard arUco dictionary
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
parameters = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Detect arUco markers in the frame
    corners, ids, rejected = detector.detectMarkers(frame)
    if ids is not None:
        for i, corner in enumerate(corners):
            pts = corner[0].astype(int)
            # Draw bounding box
            for j in range(4):
                cv2.line(frame, tuple(pts[j]), tuple(pts[(j+1)%4]), (0,255,0), 2)
            # Show marker ID and coordinates
            marker_id = int(ids[i])
            cv2.putText(frame, f'ID:{marker_id}', tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,0,0), 2)
            print(f'arUco ID: {marker_id}, Coords: {pts.tolist()}')

    # Show video feed
    cv2.imshow('arUco Marker Scanner', frame)

    # Exit on 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
