import asyncio
import websockets
import json
import threading
import time
from typing import Dict, Optional, Callable, Any

class WebSocketClient:
    def __init__(self, uri: str):
        """
        Initialize WebSocket client
        
        Args:
            uri: WebSocket server URI (e.g., "ws://localhost:8080")
        """
        self.uri = uri
        self.websocket = None
        self.running = False
        self.loop = None
        self.thread = None
        
        # Storage for received ArUco data
        self.aruco_data: Dict[int, Any] = {}
        
        # Callbacks
        self.on_aruco_received: Optional[Callable[[Dict[int, Any]], None]] = None
        self.on_message_received: Optional[Callable[[str], None]] = None
        self.on_connected: Optional[Callable[[], None]] = None
        self.on_disconnected: Optional[Callable[[], None]] = None
    
    def set_aruco_callback(self, callback: Callable[[Dict[int, Any]], None]):
        """Set callback for when ArUco data is received"""
        self.on_aruco_received = callback
    
    def set_message_callback(self, callback: Callable[[str], None]):
        """Set callback for any message received"""
        self.on_message_received = callback
    
    def set_connection_callbacks(self, on_connected: Callable[[], None] = None, 
                               on_disconnected: Callable[[], None] = None):
        """Set callbacks for connection events"""
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
    
    def _parse_message(self, message: str) -> bool:
        """
        Parse incoming message and extract ArUco data
        
        Expected format examples:
        - {"aruco_id": 5, "data": "some_data"}
        - {"aruco_ids": [1, 2, 3], "data": {"key": "value"}}
        - {"command": "reset"}
        
        Returns True if ArUco data was found and processed
        """
        try:
            data = json.loads(message)
            
            # Handle single ArUco ID
            if "aruco_id" in data:
                aruco_id = int(data["aruco_id"])
                payload = data.get("data", None)
                self.aruco_data[aruco_id] = payload
                print(f"Received ArUco ID {aruco_id} with data: {payload}")
                return True
            
            # Handle multiple ArUco IDs
            elif "aruco_ids" in data:
                aruco_ids = data["aruco_ids"]
                payload = data.get("data", None)
                for aruco_id in aruco_ids:
                    self.aruco_data[int(aruco_id)] = payload
                print(f"Received ArUco IDs {aruco_ids} with data: {payload}")
                return True
            
            # Handle reset command
            elif data.get("command") == "reset":
                self.aruco_data.clear()
                print("ArUco data cleared")
                return True
            
            # Handle clear specific ID
            elif data.get("command") == "clear" and "aruco_id" in data:
                aruco_id = int(data["aruco_id"])
                if aruco_id in self.aruco_data:
                    del self.aruco_data[aruco_id]
                    print(f"Cleared ArUco ID {aruco_id}")
                return True
                
        except json.JSONDecodeError:
            print(f"Invalid JSON received: {message}")
        except (KeyError, ValueError, TypeError) as e:
            print(f"Error parsing message: {e}")
        
        return False
    
    async def _listen(self):
        """Listen for incoming WebSocket messages"""
        try:
            async with websockets.connect(self.uri) as websocket:
                self.websocket = websocket
                print(f"Connected to WebSocket: {self.uri}")
                
                if self.on_connected:
                    self.on_connected()
                
                async for message in websocket:
                    if not self.running:
                        break
                    
                    print(f"Received message: {message}")
                    
                    # Call general message callback
                    if self.on_message_received:
                        self.on_message_received(message)
                    
                    # Parse and handle ArUco data
                    if self._parse_message(message):
                        # Call ArUco-specific callback
                        if self.on_aruco_received:
                            self.on_aruco_received(self.aruco_data.copy())
                
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            self.websocket = None
            if self.on_disconnected:
                self.on_disconnected()
    
    def _run_event_loop(self):
        """Run the asyncio event loop in a separate thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            while self.running:
                try:
                    self.loop.run_until_complete(self._listen())
                except Exception as e:
                    print(f"Connection error: {e}")
                
                if self.running:
                    print("Attempting to reconnect in 5 seconds...")
                    time.sleep(5)
        finally:
            self.loop.close()
    
    def start(self):
        """Start the WebSocket client"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        print(f"WebSocket client started, connecting to {self.uri}")
    
    def stop(self):
        """Stop the WebSocket client"""
        self.running = False
        
        if self.websocket:
            asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)
        
        if self.thread:
            self.thread.join(timeout=5)
        
        print("WebSocket client stopped")
    
    def get_aruco_data(self) -> Dict[int, Any]:
        """Get current ArUco data"""
        return self.aruco_data.copy()
    
    def clear_aruco_data(self):
        """Clear all stored ArUco data"""
        self.aruco_data.clear()
    
    def send_message(self, message: str):
        """Send a message to the WebSocket server"""
        if self.websocket and self.loop:
            asyncio.run_coroutine_threadsafe(
                self.websocket.send(message), 
                self.loop
            )
    
    def send_json(self, data: dict):
        """Send JSON data to the WebSocket server"""
        self.send_message(json.dumps(data))
