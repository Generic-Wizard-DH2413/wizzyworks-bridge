import base64
import cv2
import time
import signal
import sys
import json
import os
import argparse
from dotenv import load_dotenv
from aruco_scanner import ArucoScanner
from websocket_client import WebSocketClient


class WizzyWorksBridge:
    def __init__(self, websocket_uri: str = "ws://localhost:8080/", camera_index: int = 0):
        """
        Main application class that coordinates WebSocket and ArUco scanning

        Args:
            websocket_uri: WebSocket server URI
            camera_index: Camera device index (0 for built-in webcam, 1+ for external)
        """
        self.websocket_uri = websocket_uri

        # Initialize components
        self.websocket_client = WebSocketClient(websocket_uri)
        self.aruco_scanner = ArucoScanner(
            camera_index=camera_index,
        )

        # Set up callbacks
        self._setup_callbacks()

        # Application state
        self.running = False

    def _setup_callbacks(self):
        """Set up callbacks between components"""

        # When a message is received via WebSocket, validate it and send confirmation
        def on_message_received(message):
            try:
                message_data = json.loads(message)
            except json.JSONDecodeError:
                print(f"❌ Error decoding JSON: {message}")
                return

            if self._validate_data(message_data):
                print("✅ Data format is valid.")
                status_message = {"id": message_data["id"], "data": {"id": message_data["id"], "status": "ready"}}
                self.websocket_client.send_json(status_message)
                print(f"✅ Sent 'ready' status for id {message_data['id']} to server.")

                # Pass validated data to ArUco scanner
                aruco_id = message_data.get("id")
                if aruco_id is not None:
                    self.aruco_scanner.set_target_id(aruco_id, message_data)
            else:
                print("❌ Data validation failed. Skipping.")

        # When an ArUco data is received via WebSocket, update scanner targets
        def on_aruco_received(aruco_id, data):
            print(f"🔔 Received ArUco ID {aruco_id} with data: {data}")
            self.aruco_scanner.set_target_id(aruco_id, data)

        # When a aruco marker is detected, trigger action
        def on_marker_detected(marker_id, associated_data, normalized_x):
            print(f"🎯 TRIGGER: ArUco marker {marker_id} detected!")
            print(f"   Associated data: {associated_data}")
            print(f"   Normalized X: {normalized_x}")
            self._handle_marker_detected(marker_id, associated_data, normalized_x)

        # Connection status callbacks
        def on_connected():
            print("✅ Connected to WebSocket server")

        def on_disconnected():
            print("❌ Disconnected from WebSocket server")

        # Set callbacks
        self.websocket_client.set_message_callback(on_message_received)
        self.websocket_client.set_aruco_callback(on_aruco_received)
        self.websocket_client.set_connection_callbacks(on_connected, on_disconnected)
        self.aruco_scanner.set_marker_detected_callback(on_marker_detected)

    def _validate_data(self, data):
        """Validate the structure and types of the received data."""
        if not isinstance(data, dict):
            print("❌ Error: Data is not a dictionary.")
            return False

        if "fireworks" not in data or not isinstance(data["fireworks"], list):
            print("❌ Error: Missing or invalid 'fireworks' list.")
            return False

        for i, firework in enumerate(data["fireworks"]):
            if not isinstance(firework, dict):
                print(f"❌ Error: Firework at index {i} is not a dictionary.")
                return False

            required_keys = {
                "outer_layer": str,
                "outer_layer_color": list,
                "outer_layer_second_color": list,
                # "inner_layer": str,
                "outer_layer_specialfx": (int, float),
                "path_speed": (int, float),
                # "path_wobble": (int, float),
            }

            for key, key_type in required_keys.items():
                if key not in firework or not isinstance(firework[key], key_type):
                    print(f"❌ Error: Missing or invalid '{key}' in firework at index {i}.")
                    return False

            for key in ["outer_layer_color", "outer_layer_second_color"]:
                if len(firework[key]) != 3 or not all(
                    isinstance(c, (int, float)) and 0 <= c <= 1 for c in firework[key]
                ):
                    print(f"❌ Error: Invalid color format for '{key}' in firework at index {i}.")
                    return False

            if not (0 <= firework["outer_layer_specialfx"] <= 1):
                print(f"❌ Error: Invalid 'outer_layer_specialfx' value in firework at index {i}.")
                return False

        return True

    def _handle_marker_detected(
        self, marker_id: int, associated_data, normalized_x: float
    ):
        """
        Handle when an ArUco marker is detected.
        Validates the data, saves the inner_layer as PNGs for each firework, and saves the
        remaining metadata as a JSON file.
        """
        # If it's a string, try to parse it as JSON
        if isinstance(associated_data, str):
            try:
                associated_data = json.loads(associated_data)
            except json.JSONDecodeError as e:
                print(f"❌ Error parsing JSON: {e}")
                return

        # Check if associated_data is valid
        if associated_data is None or not isinstance(associated_data, dict):
            print(f"❌ Invalid associated_data for marker {marker_id}: {associated_data}")
            return

        # Check if fireworks key exists
        if "fireworks" not in associated_data or not isinstance(associated_data["fireworks"], list):
            print(f"❌ Missing or invalid 'fireworks' list in associated_data for marker {marker_id}")
            return

        # Create save directory path
        save_dir = "C:\\Users\\lambo\\Developer\\wizzyworks-graphics\\godot-visuals\\json_fireworks"
        os.makedirs(save_dir, exist_ok=True)

        # Create folder for this marker ID
        id_folder = os.path.join(save_dir, "firework_drawings", str(marker_id))
        os.makedirs(id_folder, exist_ok=True)

        # --- Save PNGs from Base64 data for each firework ---
        successful_pngs = []

        for index, firework in enumerate(associated_data["fireworks"]):
            if not firework.get("inner_layer"):
                print(f"Skipping PNG creation for marker {marker_id}, firework {index} (no inner_layer)")
                continue
            
            png_filename = os.path.join(id_folder, f"{index}.png")
            
            try:
                # Delete any existing .png.import file before creating the PNG (Godot auto-generated import file)
                import_filename = f"{png_filename}.import"
                if os.path.exists(import_filename):
                    try:
                        os.remove(import_filename)
                        print(f"🗑️ Deleted existing import file: {import_filename}")
                    except Exception as e:
                        print(f"⚠️ Warning: Could not delete import file {import_filename}: {e}")
                
                # Decode the Base64 string
                base64_string = firework["inner_layer"]
                print(f"Decoding Base64 string for marker {marker_id}, firework {index}...")
                print(f"Base64 string length: {len(base64_string)}")
                print(f"First 100 characters of Base64 string: {base64_string[:100]}")
                
                # Check if it's a data URL and extract just the Base64 part
                if base64_string.startswith("data:"):
                    # Split on comma and take the part after it (the actual Base64 data)
                    if "," in base64_string:
                        base64_string = base64_string.split(",", 1)[1]
                        print(f"Extracted Base64 data (length: {len(base64_string)})")
                    else:
                        print("⚠️ Warning: Data URL format detected but no comma separator found")
                
                image_data = base64.b64decode(base64_string)

                # Save to PNG file
                with open(png_filename, "wb") as f:
                    f.write(image_data)

                # Verify the PNG file was created and has content
                if os.path.exists(png_filename) and os.path.getsize(png_filename) > 0:
                    print(f"💾 Saved marker {marker_id} firework {index} image to {png_filename}")
                    successful_pngs.append(index)
                else:
                    print(f"❌ PNG file created but appears to be empty: {png_filename}")

            except (base64.binascii.Error, TypeError) as e:
                print(f"❌ Error decoding Base64 string for marker {marker_id}, firework {index}: {e}")
            except Exception as e:
                print(f"❌ Error saving PNG for marker {marker_id}, firework {index}: {e}")

        # --- Save metadata to JSON file ---
        # Add delay after PNG generation before creating JSON (only if any PNGs were created)
        if successful_pngs:
            time.sleep(5.5)
        
        json_filename = os.path.join(save_dir, f"{marker_id}.json")
        try:
            # Create the fireworks list with modified inner_layer and added location
            fireworks_metadata = []
            for idx, fw in enumerate(associated_data["fireworks"]):
                firework_copy = json.loads(json.dumps(fw))
                if idx in successful_pngs:
                    firework_copy["inner_layer"] = f"{marker_id}/{idx}.png"
                else:
                    firework_copy["inner_layer"] = None
                firework_copy["location"] = normalized_x
                fireworks_metadata.append(firework_copy)

            # Save the fireworks list as the root of the JSON
            with open(json_filename, "w") as f:
                json.dump(fireworks_metadata, f, indent=4)

            print(f"💾 Saved marker {marker_id} metadata to {json_filename}")

            # Send launch status back to frontend
            launch_message = {"id": marker_id, "data": {"id": marker_id, "status": "launch"}}
            self.websocket_client.send_json(launch_message)
            print(f"🚀 Sent 'launch' status for id {marker_id} to server.")

        except Exception as e:
            print(f"❌ Error saving JSON for marker {marker_id}: {e}")

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
        window_name = "WizzyWorks Bridge - ArUco Scanner"
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
                if key == ord("q"):
                    break
                elif key == ord("r"):
                    # Reset triggered markers
                    self.aruco_scanner.reset_triggered_ids()
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
        cv2.rectangle(
            overlay, (10, 10), (10 + overlay_width, 10 + overlay_height), (0, 0, 0), -1
        )
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Status text
        target_ids = list(self.aruco_scanner.get_target_ids().keys())

        y_offset = int(30 * scale_factor)
        cv2.putText(
            frame,
            f"WebSocket: {self.websocket_uri}",
            (15, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (0, 255, 0),
            thickness,
        )

        y_offset += int(20 * scale_factor)
        cv2.putText(
            frame,
            f"Target IDs: {target_ids}",
            (15, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (0, 255, 255),
            thickness,
        )

        y_offset += int(20 * scale_factor)
        cv2.putText(
            frame,
            "Controls: 'q'=quit, 'r'=reset, 'c'=clear",
            (15, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale * 0.8,
            (255, 255, 255),
            thickness,
        )

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
    # Load environment variables from .env file
    load_dotenv()
    
    # Set up command-line argument parser
    parser = argparse.ArgumentParser(description='WizzyWorks Bridge - ArUco Scanner with WebSocket')
    parser.add_argument(
        '--camera', '-c',
        type=int,
        default=int(os.getenv('CAMERA_INDEX', 0)),
        help='Camera index (0 for built-in webcam, 1+ for external cameras). Default: 0 or CAMERA_INDEX env var'
    )
    parser.add_argument(
        '--websocket-uri', '-w',
        type=str,
        default=os.getenv('WEBSOCKET_URI', 'wss://wizzyworks-server.redbush-85e59e10.swedencentral.azurecontainerapps.io'),
        help='WebSocket URI. Default: WEBSOCKET_URI env var or production server'
    )
    
    args = parser.parse_args()
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    # Configuration from command-line args and environment variables
    websocket_uri = args.websocket_uri
    camera_index = args.camera
    
    print(f"🔧 Configuration:")
    print(f"   WebSocket URI: {websocket_uri}")
    print(f"   Camera Index: {camera_index}")
    print()

    # Create and start the bridge
    bridge = WizzyWorksBridge(websocket_uri, camera_index)
    bridge.start()


if __name__ == "__main__":
    main()
