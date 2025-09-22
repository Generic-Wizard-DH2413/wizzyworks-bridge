# WizzyWorks Bridge

A Python application that bridges WebSocket communication with ArUco marker detection. The system listens for ArUco marker IDs via WebSocket, then monitors a video feed for those specific markers. When a marker is detected and remains stable (not moving) for a specified duration, it triggers a custom action.

## Features

- **WebSocket Integration**: Receives ArUco marker IDs and associated data via WebSocket
- **Real-time ArUco Detection**: Continuously scans video feed for ArUco markers
- **Stability Detection**: Only triggers actions when markers are stationary for a configured duration
- **Component-based Architecture**: Modular design with separate scanner and WebSocket components
- **Visual Feedback**: Live video feed with marker detection overlay and status information
- **Test Server Included**: Complete testing environment with interactive commands

## Architecture

### Components

1. **`aruco_scanner.py`**: ArUco marker detection and stability tracking
2. **`websocket_client.py`**: WebSocket client for receiving marker data
3. **`main.py`**: Main application coordinating all components
4. **`test_server.py`**: WebSocket server for testing and development
5. **`demo.py`**: Demonstration script showing usage examples

### Data Flow

1. WebSocket server sends ArUco marker IDs with associated data
2. Bridge receives and stores the target marker IDs
3. Camera continuously scans for ArUco markers
4. When a target marker is detected and stable, triggers custom action
5. Action results can be sent back via WebSocket

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd wizzyworks-bridge
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify camera access**:
   Make sure your camera is connected and accessible by OpenCV.

## Quick Start

### 1. Start the Test Server

Open a terminal and run:
```bash
python test_server.py
```

This starts a WebSocket server on `ws://localhost:8080` with interactive mode.

### 2. Start the Bridge Application

In another terminal, run:
```bash
python main.py
```

This will:
- Connect to the WebSocket server
- Start the camera feed
- Begin monitoring for ArUco markers

### 3. Send ArUco Commands

In the test server terminal, you can use these commands:

```bash
# Send a single ArUco ID with data
send 1 red_button

# Send multiple ArUco IDs
multi 1,2,3

# Reset all stored IDs
reset

# Clear a specific ID
clear 1
```

### 4. Test with Physical Markers

1. Generate ArUco markers using online tools or OpenCV
2. Print markers with IDs that match your WebSocket commands
3. Show markers to the camera
4. Keep markers stable (not moving) for 2 seconds
5. Watch for trigger events in the console

## Configuration

### Camera Settings

In `aruco_scanner.py`, you can adjust:

```python
# Camera resolution
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

# Exposure settings (for bright markers in dark rooms)
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
cap.set(cv2.CAP_PROP_EXPOSURE, 100)
```

### Stability Detection

In `main.py`, adjust the scanner parameters:

```python
self.aruco_scanner = ArucoScanner(
    camera_index=0,
    stability_threshold=10.0,  # pixels (how much movement is allowed)
    stability_duration=2.0     # seconds (how long marker must be stable)
)
```

### WebSocket URI

Change the WebSocket server address in `main.py`:

```python
websocket_uri = "ws://your-server:8080"
```

## WebSocket Message Format

The system expects JSON messages in these formats:

### Single ArUco ID
```json
{
    "aruco_id": 5,
    "data": "any_data_here"
}
```

## Custom Actions

To implement your custom logic when markers are detected, modify the `_handle_stable_marker` method in `main.py`:

```python
def _handle_stable_marker(self, marker_id: int, associated_data):
    """Handle when a stable ArUco marker is detected"""
    
    # Your custom logic here
    if marker_id == 1:
        # Control hardware, send API calls, etc.
        print("Executing red button action!")
    elif marker_id == 2:
        # Different action for different markers
        print("Executing blue button action!")
    
    # Send confirmation back to WebSocket
    response = {
        "event": "marker_triggered",
        "marker_id": marker_id,
        "data": associated_data,
        "timestamp": time.time()
    }
    self.websocket_client.send_json(response)
```

## Controls

When the video window is active:

- **`q`**: Quit the application
- **`r`**: Reset triggered markers (allows re-triggering)
- **`c`**: Clear all stored ArUco data

## Troubleshooting

### Camera Issues

1. **No camera detected**: Check camera index in `ArucoScanner(camera_index=0)`
2. **Poor detection**: Adjust lighting and camera exposure settings
3. **Low resolution**: Increase camera resolution settings

### WebSocket Issues

1. **Connection failed**: Verify WebSocket server is running and URI is correct
2. **Messages not received**: Check JSON format and network connectivity
3. **Reconnection problems**: Server automatically attempts reconnection every 5 seconds

### ArUco Detection Issues

1. **Markers not detected**: Ensure good lighting and proper marker size
2. **False triggers**: Increase `stability_threshold` or `stability_duration`
3. **Missing triggers**: Decrease stability parameters or improve marker visibility

## Development

### Adding New Features

1. **Custom message types**: Modify `_parse_message` in `websocket_client.py`
2. **Different stability algorithms**: Extend `_is_marker_stable` in `aruco_scanner.py`
3. **Additional camera sources**: Create new scanner instances with different indices

### Testing

Run the demo script to test the complete workflow:

```bash
python demo.py
```

This sends a sequence of test commands to demonstrate all features.

## Dependencies

- **OpenCV**: Computer vision and ArUco marker detection
- **NumPy**: Numerical operations
- **websockets**: WebSocket client/server functionality
