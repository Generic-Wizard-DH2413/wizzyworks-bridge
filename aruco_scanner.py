import cv2
import numpy as np
import threading
import time
import platform
from collections import defaultdict
from typing import Any, Dict, List, Tuple, Optional, Callable


class ArucoScanner:
    def __init__(
        self,
        camera_index: int = 0,
    ):
        """
        Initialize ArUco scanner

        Args:
            camera_index: Camera device index
        """
        self.camera_index = camera_index

        # OS-specific camera setup
        self.os_name = platform.system()
        self.is_windows = self.os_name == "Windows"
        self.is_linux = self.os_name == "Linux"
        self.is_macos = self.os_name == "Darwin"
        
        if self.is_windows:
            # Windows setup - use DirectShow backend
            self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            print("Using DirectShow backend for Windows")
        elif self.is_linux:
            # Linux setup - use V4L2 backend for better Linux compatibility
            self.cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
            print("Using V4L2 backend for Linux")
        elif self.is_macos:
            # macOS setup - use AVFoundation backend
            self.cap = cv2.VideoCapture(camera_index, cv2.CAP_AVFOUNDATION)
            print("Using AVFoundation backend for macOS")
        else:
            # Fallback for unknown OS - use default backend
            self.cap = cv2.VideoCapture(camera_index)
            print(f"Using default backend for unknown OS: {self.os_name}")

        # Set pixel format to MJPG to avoid color issues
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*"MJPG"))

        # Set desired resolution and frame rate
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        # OS-specific exposure settings
        if self.is_windows:
            # Windows DirectShow exposure settings
            # For DirectShow, auto exposure modes: 0.25 = manual, 0.75 = auto
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual mode for DirectShow
            self.cap.set(cv2.CAP_PROP_EXPOSURE, -6)  # Negative values for DirectShow (typically -13 to -1)
        elif self.is_linux:
            # Linux V4L2 exposure settings
            # Disable auto exposure (1 = manual mode for V4L2) and set a manual exposure value
            # A lower value means shorter exposure, darker image, and higher framerate potential
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # Manual mode for V4L2
            self.cap.set(cv2.CAP_PROP_EXPOSURE, 100)
        elif self.is_macos:
            # macOS AVFoundation exposure settings
            # Similar to DirectShow but may have different optimal values
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual mode for AVFoundation
            self.cap.set(cv2.CAP_PROP_EXPOSURE, -5)  # Slightly different exposure for macOS
        else:
            # Fallback exposure settings for unknown OS
            # Try common values that might work across platforms
            try:
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Try DirectShow-style first
                self.cap.set(cv2.CAP_PROP_EXPOSURE, -6)
                print("Using DirectShow-style exposure settings as fallback")
            except:
                try:
                    self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # Fallback to V4L2-style
                    self.cap.set(cv2.CAP_PROP_EXPOSURE, 100)
                    print("Using V4L2-style exposure settings as fallback")
                except:
                    print("Warning: Could not set exposure settings - using camera defaults")

        # Verify settings
        fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
        actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        actual_auto_exposure = self.cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)
        actual_exposure = self.cap.get(cv2.CAP_PROP_EXPOSURE)

        print("--- Camera Settings ---")
        backend_info = {
            "Windows": "DirectShow (Windows)",
            "Linux": "V4L2 (Linux)", 
            "Darwin": "AVFoundation (macOS)",
        }.get(self.os_name, f"Default ({self.os_name})")
        print(f"Backend: {backend_info}")
        print(f"FOURCC set: MJPG, actual: {fourcc_str}")
        print(
            f"Resolution set: 1920x1080, actual: {int(actual_width)}x{int(actual_height)}"
        )
        print(f"FPS set: 30, actual: {actual_fps}")
        
        if self.is_windows:
            print(f"Auto Exposure set to: 0.25 (Manual), actual: {actual_auto_exposure}")
            print(f"Exposure set to: -6, actual: {actual_exposure}")
        elif self.is_linux:
            print(f"Auto Exposure set to: 1 (Manual), actual: {actual_auto_exposure}")
            print(f"Exposure set to: 100, actual: {actual_exposure}")
        elif self.is_macos:
            print(f"Auto Exposure set to: 0.25 (Manual), actual: {actual_auto_exposure}")
            print(f"Exposure set to: -5, actual: {actual_exposure}")
        else:
            print(f"Auto Exposure (fallback), actual: {actual_auto_exposure}")
            print(f"Exposure (fallback), actual: {actual_exposure}")
        print("-----------------------")

        # ArUco detection setup
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)

        # Tracking data
        self.marker_positions: Dict[int, List[Tuple[float, float, float]]] = (
            defaultdict(list)
        )  # id -> [(x, y, timestamp), ...]
        self.target_ids: Dict[
            int, Any
        ] = {}  # ArUco IDs to watch for with their associated data
        self.triggered_ids: set = set()  # Keep track of already triggered IDs

        # Threading
        self.running = False
        self.scan_thread = None
        self.frame_lock = threading.Lock()
        self.latest_frame = None

        # Callback for when marker is detected
        self.on_marker_detected: Optional[Callable[[int, Any, float], None]] = None

    def set_target_id(self, new_id: int, data: Any):
        """Add or update a single ArUco ID to watch for with its associated data"""
        self.target_ids[new_id] = data
        self.triggered_ids.discard(
            new_id
        )  # Allow retriggering if it was already triggered
        print(f"Added/Updated target ArUco ID: {new_id}")
        print(f"Current target ArUco IDs: {list(self.target_ids.keys())}")
        print(f"Current triggered ArUco IDs: {list(self.triggered_ids)}")

    def get_target_ids(self) -> Dict[int, Any]:
        """Get the current target ArUco IDs and their associated data"""
        return self.target_ids.copy()

    def set_marker_detected_callback(self, callback: Callable[[int, Any, float], None]):
        """Set the callback function to call when a aruco marker is detected"""
        self.on_marker_detected = callback

    def _calculate_marker_center(self, corners) -> Tuple[float, float]:
        """Calculate the center point of a marker from its corners"""
        center_x = np.mean(corners[0][:, 0])
        center_y = np.mean(corners[0][:, 1])
        return float(center_x), float(center_y)

    def _scan_loop(self):
        """Main scanning loop running in a separate thread"""
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            # Detect ArUco markers
            corners, ids, rejected = self.detector.detectMarkers(frame)

            # DEBUG: Print detection info
            if ids is not None:
                detected_ids = [int(id_val) for id_val in ids.flatten()]
                # print(f"🔍 DEBUG: Detected ArUco markers: {detected_ids}")
            else:
                # Only print this occasionally to avoid spam
                if not hasattr(self, "_last_no_detection_print"):
                    self._last_no_detection_print = 0
                current_time = time.time()
                if (
                    current_time - self._last_no_detection_print > 5
                ):  # Print every 5 seconds
                    # print("🔍 DEBUG: No ArUco markers detected in frame")
                    self._last_no_detection_print = current_time

            if ids is not None:
                for i, corner in enumerate(corners):
                    marker_id = int(ids[i])

                    # Only process markers we're looking for
                    if marker_id in self.target_ids:
                        center = self._calculate_marker_center(corner)
                        frame_height, frame_width = frame.shape[:2]
                        center_x, center_y = self._calculate_marker_center(corner)
                        normalized_x = (center_x / frame_width) * 2 - 1

                        if marker_id not in self.triggered_ids:
                            # print(f"🎯 DEBUG: ArUco marker detected immediately: ID {marker_id}")
                            self.triggered_ids.add(marker_id)

                            # Trigger callback if set
                            if self.on_marker_detected:
                                try:
                                    self.on_marker_detected(
                                        marker_id,
                                        self.target_ids[marker_id],
                                        normalized_x,
                                    )
                                except Exception as e:
                                    print(f"Error in marker callback: {e}")

                        # Draw marker on frame
                        pts = corner[0].astype(int)
                        for j in range(4):
                            cv2.line(
                                frame,
                                tuple(pts[j]),
                                tuple(pts[(j + 1) % 4]),
                                (0, 255, 0),
                                2,
                            )

                        # Draw vertical line across entire screen height
                        cv2.line(
                            frame,
                            (int(center_x), 0),
                            (int(center_x), frame_height),
                            (0, 0, 255),
                            3,
                        )

                        # Show marker ID and status
                        status = (
                            "TRIGGERED"
                            if marker_id in self.triggered_ids
                            else "TRACKING"
                        )
                        color = (
                            (0, 0, 255)
                            if marker_id in self.triggered_ids
                            else (255, 0, 0)
                        )
                        cv2.putText(
                            frame,
                            f"ID:{marker_id} {status} X:{normalized_x:.2f}",
                            tuple(pts[0]),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            color,
                            2,
                        )

                    # TEMPORARY: Also show ALL detected markers for debugging, even if not in target list
                    else:
                        pts = corner[0].astype(int)
                        for j in range(4):
                            cv2.line(
                                frame,
                                tuple(pts[j]),
                                tuple(pts[(j + 1) % 4]),
                                (128, 128, 128),
                                1,
                            )

                        # Draw red line through middle of marker
                        center_x, center_y = self._calculate_marker_center(corner)
                        frame_height, frame_width = frame.shape[:2]
                        # Draw vertical line across entire screen height
                        cv2.line(
                            frame,
                            (int(center_x), 0),
                            (int(center_x), frame_height),
                            (0, 0, 255),
                            2,
                        )

                        # Calculate normalized x coordinate (-1 to 1)
                        normalized_x = (center_x / frame_width) * 2 - 1
                        # print(f"🔍 Non-target Marker ID {marker_id}: normalized_x = {normalized_x:.3f}")

                        cv2.putText(
                            frame,
                            f"ID:{marker_id} NOT_TARGET X:{normalized_x:.2f}",
                            tuple(pts[0]),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (128, 128, 128),
                            1,
                        )
                        # print(f"🔍 DEBUG: Detected non-target ArUco marker: ID {marker_id}")

            # Clean up old position data for markers not currently visible
            # current_ids = (
            #     set(int(id_val) for id_val in ids) if ids is not None else set()
            # )
            # for marker_id in list(self.marker_positions.keys()):
            #     if marker_id not in current_ids:
            #         # Remove positions older than stability_duration * 2
            #         current_time = time.time()
            #         self.marker_positions[marker_id] = [
            #             (x, y, t)
            #             for x, y, t in self.marker_positions[marker_id]
            #             if current_time - t <= self.stability_duration * 2
            #         ]
            #         if not self.marker_positions[marker_id]:
            #             del self.marker_positions[marker_id]

            # Store latest frame for display (after all drawing is complete)
            with self.frame_lock:
                self.latest_frame = frame.copy()

            # Small delay to prevent excessive CPU usage
            time.sleep(0.01)

    def start(self):
        """Start the scanning process"""
        if self.running:
            return

        self.running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        print("ArUco scanner started")

    def stop(self):
        """Stop the scanning process"""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join()
        self.cap.release()
        print("ArUco scanner stopped")

    def get_latest_frame(self):
        """Get the latest frame for display"""
        with self.frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None

    def reset_triggered_ids(self):
        """Reset the triggered IDs list - allows markers to be triggered again"""
        self.triggered_ids.clear()
        print("Reset triggered ArUco IDs")
