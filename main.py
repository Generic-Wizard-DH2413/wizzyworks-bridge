import cv2
import time
import signal
import sys
import json
import os
from aruco_scanner import ArucoScanner
from websocket_client import WebSocketClient

class WizzyWorksBridge:
    def __init__(self, websocket_uri: str = "ws://localhost:8080/"):
        """
        Main application class that coordinates WebSocket and ArUco scanning
        
        Args:
            websocket_uri: WebSocket server URI
        """
        self.websocket_uri = websocket_uri
        
        # Initialize components
        self.websocket_client = WebSocketClient(websocket_uri)
        self.aruco_scanner = ArucoScanner(
            camera_index=0,
            stability_threshold=10.0,  # pixels
            stability_duration=2.0     # seconds
        )
        
        # Set up callbacks
        self._setup_callbacks()
        
        # Application state
        self.running = False
    
    def _setup_callbacks(self):
        """Set up callbacks between components"""
        
        # When ArUco data is received via WebSocket, update scanner targets
        def on_aruco_received(aruco_data):
            print(f"Updating ArUco targets: {list(aruco_data.keys())}")
            self.aruco_scanner.set_target_ids(aruco_data)
        
        # When a stable marker is detected, trigger action
        def on_stable_marker(marker_id, associated_data, normalized_x):
            print(f"🎯 TRIGGER: Stable ArUco marker {marker_id} detected!")
            print(f"   Associated data: {associated_data}")
            print(f"   Normalized X: {normalized_x}")
            self._handle_stable_marker(marker_id, associated_data, normalized_x)  # normalized_x can be implemented as needed
        
        # Connection status callbacks
        def on_connected():
            print("✅ Connected to WebSocket server")
        
        def on_disconnected():
            print("❌ Disconnected from WebSocket server")
        
        # Set callbacks
        self.websocket_client.set_aruco_callback(on_aruco_received)
        self.websocket_client.set_connection_callbacks(on_connected, on_disconnected)
        self.aruco_scanner.set_stable_marker_callback(on_stable_marker)
    
    def _handle_stable_marker(self, marker_id: int, associated_data, normolized_x: float):
        """
        Handle when a stable ArUco marker is detected
        This is where you implement your custom logic
        
        Args:
            marker_id: The ArUco marker ID that was detected
            associated_data: Any data that was sent with this marker ID via WebSocket
        """
        # Check if associated_data is a list of x,y coordinates
        print(f"🔍 Debug: associated_data type: {type(associated_data)}")
        print(f"🔍 Debug: associated_data value: {associated_data}")
        
        # If it's a string, try to parse it as JSON
        if isinstance(associated_data, str):
            try:
                associated_data = json.loads(associated_data)
                print(f"🔍 Debug: Parsed JSON successfully: {associated_data}")
            except json.JSONDecodeError as e:
                print(f"❌ Error parsing JSON: {e}")
                print(f"ℹ️ Marker {marker_id} data is not valid JSON - skipping file save")
                return
        
        print(f"🔍 Debug: isinstance(associated_data, list): {isinstance(associated_data, list)}")
        
        if isinstance(associated_data, list) and len(associated_data) > 0:
            print(f"🔍 Debug: Passed initial list check, length: {len(associated_data)}")
            # Validate that all items in the list are coordinate pairs (x,y)
            is_coordinate_list = True
            for i, item in enumerate(associated_data):
                print(f"🔍 Debug: Item {i}: {item}, type: {type(item)}")
                item_is_valid = (isinstance(item, (list, tuple)) and len(item) == 2 and 
                               all(isinstance(coord, (int, float)) for coord in item))
                print(f"🔍 Debug: Item {i} is valid: {item_is_valid}")
                if not item_is_valid:
                    is_coordinate_list = False
                    break
            
            print(f"🔍 Debug: is_coordinate_list: {is_coordinate_list}")
            if is_coordinate_list:
                # Create the data structure to save
                data_to_save = {
                    "location": normolized_x,
                    "points": associated_data
                }
                
                # Create save directory path
                save_dir = "../wizzyworks-graphics/godot-visuals/json_fireworks"
                
                # Create directory if it doesn't exist
                os.makedirs(save_dir, exist_ok=True)
                
                # Create filename based on marker ID
                filename = os.path.join(save_dir, f"{marker_id}.json")
                
                try:
                    # Save to JSON file
                    with open(filename, 'w') as f:
                        json.dump(data_to_save, f, indent=2)
                    
                    print(f"💾 Saved marker {marker_id} data to {filename}")
                    print(f"   Location: {normolized_x}")
                    print(f"   Points: {len(associated_data)} coordinate pairs")
                    
                except Exception as e:
                    print(f"❌ Error saving data for marker {marker_id}: {e}")
            else:
                print(f"⚠️ Marker {marker_id} data is not a valid list of x,y coordinates")
        else:
            print(f"ℹ️ Marker {marker_id} data is not a list - skipping file save")
                
    
    def start(self):
        """Start the bridge application"""
        print("🚀 Starting WizzyWorks Bridge...")
        print(f"WebSocket URI: {self.websocket_uri}")
        print("📺 Video window is resizable - drag corners to adjust size")
        print("Press 'q' in the video window or Ctrl+C to exit")
        
        self.running = True
        
        # Start components
        self.websocket_client.start()
        time.sleep(1)  # Give WebSocket time to connect
        self.aruco_scanner.start()
        
        # Main display loop
        try:
            self._display_loop()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
        finally:
            self.stop()
    
    def _display_loop(self):
        """Main loop for displaying video feed"""
        # Create window with resizable property
        window_name = 'WizzyWorks Bridge - ArUco Scanner'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        # Set initial window size (50% of capture resolution)
        cv2.resizeWindow(window_name, 960, 540)
        
        while self.running:
            frame = self.aruco_scanner.get_latest_frame()
            
            if frame is not None:
                # Add status information to frame
                self._add_status_overlay(frame)
                
                # Scale down frame for display to improve performance and fit screen
                # Keep original resolution for detection, but display at smaller size
                display_frame = cv2.resize(frame, (960, 540))
                
                # Display frame
                cv2.imshow(window_name, display_frame)
                
                # Handle key presses
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    # Reset triggered markers
                    self.aruco_scanner.reset_triggered_ids()
                elif key == ord('c'):
                    # Clear ArUco data
                    self.websocket_client.clear_aruco_data()
                    self.aruco_scanner.set_target_ids({})
            else:
                time.sleep(0.01)
    
    def _add_status_overlay(self, frame):
        """Add status information overlay to the frame"""
        height, width = frame.shape[:2]
        
        # Scale overlay size based on frame size
        # If frame is full resolution (1920x1080), use normal size
        # If frame is scaled down, scale overlay proportionally
        scale_factor = width / 1920.0 if width <= 1920 else 1.0
        
        overlay_width = int(400 * scale_factor)
        overlay_height = int(120 * scale_factor)
        font_scale = 0.5 * scale_factor
        thickness = max(1, int(1 * scale_factor))
        
        # Background for status text
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (10 + overlay_width, 10 + overlay_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Status text
        aruco_data = self.websocket_client.get_aruco_data()
        target_ids = list(aruco_data.keys())
        
        y_offset = int(30 * scale_factor)
        cv2.putText(frame, f"WebSocket: {self.websocket_uri}", (15, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 0), thickness)
        
        y_offset += int(20 * scale_factor)
        cv2.putText(frame, f"Target IDs: {target_ids}", (15, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 255), thickness)
        
        y_offset += int(20 * scale_factor)
        cv2.putText(frame, "Controls: 'q'=quit, 'r'=reset, 'c'=clear", (15, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.8, (255, 255, 255), thickness)
    
    def stop(self):
        """Stop the bridge application"""
        self.running = False
        self.aruco_scanner.stop()
        self.websocket_client.stop()
        cv2.destroyAllWindows()
        print("✅ WizzyWorks Bridge stopped")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Received interrupt signal...")
    sys.exit(0)

def main():
    """Main entry point"""
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # You can change the WebSocket URI here
    websocket_uri = "ws://130.229.156.85:8765"
    
    # Create and start the bridge
    bridge = WizzyWorksBridge(websocket_uri)
    bridge.start()

if __name__ == "__main__":
    main()
