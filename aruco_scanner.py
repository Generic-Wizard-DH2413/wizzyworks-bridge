import cv2
import numpy as np
import threading
import time
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Callable

class ArucoScanner:
    def __init__(self, camera_index: int = 0, stability_threshold: float = 10.0, stability_duration: float = 2.0):
        """
        Initialize ArUco scanner with stability detection
        
        Args:
            camera_index: Camera device index
            stability_threshold: Maximum pixel movement allowed for stability (pixels)
            stability_duration: How long marker must be stable before triggering (seconds)
        """
        self.camera_index = camera_index
        self.stability_threshold = stability_threshold
        self.stability_duration = stability_duration
        
        # Camera setup
        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        self.cap.set(cv2.CAP_PROP_EXPOSURE, -6)
        
        # ArUco detection setup
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)
        
        # Tracking data
        self.marker_positions: Dict[int, List[Tuple[float, float, float]]] = defaultdict(list)  # id -> [(x, y, timestamp), ...]
        self.target_ids: Dict[int, any] = {}  # ArUco IDs to watch for with their associated data
        self.triggered_ids: set = set()  # Keep track of already triggered IDs
        
        # Threading
        self.running = False
        self.scan_thread = None
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        
        # Callback for when stable marker is detected
        self.on_stable_marker: Optional[Callable[[int, any], None]] = None
    
    def set_target_ids(self, target_ids: Dict[int, any]):
        """Set the ArUco IDs to watch for with their associated data"""
        self.target_ids = target_ids.copy()
        self.triggered_ids.clear()  # Reset triggered state when new targets are set
        print(f"Updated target ArUco IDs: {list(self.target_ids.keys())}")
    
    def set_stable_marker_callback(self, callback: Callable[[int, any], None]):
        """Set the callback function to call when a stable marker is detected"""
        self.on_stable_marker = callback
    
    def _calculate_marker_center(self, corners) -> Tuple[float, float]:
        """Calculate the center point of a marker from its corners"""
        center_x = np.mean(corners[0][:, 0])
        center_y = np.mean(corners[0][:, 1])
        return float(center_x), float(center_y)
    
    def _is_marker_stable(self, marker_id: int, current_center: Tuple[float, float]) -> bool:
        """Check if a marker has been stable for the required duration"""
        current_time = time.time()
        positions = self.marker_positions[marker_id]
        
        # Add current position
        positions.append((current_center[0], current_center[1], current_time))
        
        # Remove old positions (older than stability_duration)
        positions[:] = [(x, y, t) for x, y, t in positions if current_time - t <= self.stability_duration]
        
        # Check if we have enough data points
        if len(positions) < 2:
            return False
        
        # Check if all recent positions are within threshold
        for x, y, t in positions:
            distance = np.sqrt((x - current_center[0])**2 + (y - current_center[1])**2)
            if distance > self.stability_threshold:
                return False
        
        # Check if we've been stable for the full duration
        oldest_time = min(t for _, _, t in positions)
        return (current_time - oldest_time) >= self.stability_duration
    
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
                print(f"🔍 DEBUG: Detected ArUco markers: {detected_ids}")
            else:
                # Only print this occasionally to avoid spam
                import time
                if not hasattr(self, '_last_no_detection_print'):
                    self._last_no_detection_print = 0
                current_time = time.time()
                if current_time - self._last_no_detection_print > 5:  # Print every 5 seconds
                    print("🔍 DEBUG: No ArUco markers detected in frame")
                    self._last_no_detection_print = current_time
            
            if ids is not None:
                for i, corner in enumerate(corners):
                    marker_id = int(ids[i])
                    
                    # Only process markers we're looking for
                    if marker_id in self.target_ids:
                        center = self._calculate_marker_center(corner)
                        
                        # TEMPORARY: Trigger immediately without stability check for debugging
                        if marker_id not in self.triggered_ids:
                            print(f"🎯 DEBUG: ArUco marker detected immediately: ID {marker_id}")
                            self.triggered_ids.add(marker_id)
                            
                            # Trigger callback if set
                            if self.on_stable_marker:
                                try:
                                    self.on_stable_marker(marker_id, self.target_ids[marker_id])
                                except Exception as e:
                                    print(f"Error in marker callback: {e}")
                        
                        # Draw marker on frame
                        pts = corner[0].astype(int)
                        print("matching id")
                        for j in range(4):
                            cv2.line(frame, tuple(pts[j]), tuple(pts[(j+1)%4]), (0,255,0), 2)
                        
                        # Draw red line through middle of marker
                        center_x, center_y = self._calculate_marker_center(corner)
                        frame_height, frame_width = frame.shape[:2]
                        # Draw vertical line across entire screen height
                        cv2.line(frame, (int(center_x), 0), (int(center_x), frame_height), (0,0,255), 3)
                        
                        # Calculate normalized x coordinate (-1 to 1)
                        normalized_x = (center_x / frame_width) * 2 - 1
                        print(f"🎯 Marker ID {marker_id}: normalized_x = {normalized_x:.3f}")
                        
                        # Show marker ID and status
                        status = "TRIGGERED" if marker_id in self.triggered_ids else "TRACKING"
                        color = (0, 0, 255) if marker_id in self.triggered_ids else (255, 0, 0)
                        cv2.putText(frame, f'ID:{marker_id} {status} X:{normalized_x:.2f}', tuple(pts[0]), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
                    # TEMPORARY: Also show ALL detected markers for debugging, even if not in target list
                    else:
                        pts = corner[0].astype(int)
                        print("not matching id")
                        for j in range(4):
                            cv2.line(frame, tuple(pts[j]), tuple(pts[(j+1)%4]), (128,128,128), 1)
                        
                        # Draw red line through middle of marker
                        center_x, center_y = self._calculate_marker_center(corner)
                        frame_height, frame_width = frame.shape[:2]
                        # Draw vertical line across entire screen height
                        cv2.line(frame, (int(center_x), 0), (int(center_x), frame_height), (0,0,255), 2)
                        
                        # Calculate normalized x coordinate (-1 to 1)
                        normalized_x = (center_x / frame_width) * 2 - 1
                        print(f"🔍 Non-target Marker ID {marker_id}: normalized_x = {normalized_x:.3f}")
                        
                        cv2.putText(frame, f'ID:{marker_id} NOT_TARGET X:{normalized_x:.2f}', tuple(pts[0]), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)
                        print(f"🔍 DEBUG: Detected non-target ArUco marker: ID {marker_id}")
            
            # Clean up old position data for markers not currently visible
            current_ids = set(int(id_val) for id_val in ids) if ids is not None else set()
            for marker_id in list(self.marker_positions.keys()):
                if marker_id not in current_ids:
                    # Remove positions older than stability_duration * 2
                    current_time = time.time()
                    self.marker_positions[marker_id] = [
                        (x, y, t) for x, y, t in self.marker_positions[marker_id] 
                        if current_time - t <= self.stability_duration * 2
                    ]
                    if not self.marker_positions[marker_id]:
                        del self.marker_positions[marker_id]
            
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
