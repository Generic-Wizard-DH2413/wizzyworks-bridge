import asyncio
import websockets
import json
import threading
import time
from typing import Dict, Optional, Callable, Any

from websockets.typing import Data


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
        self.loop: asyncio.AbstractEventLoop
        self.thread = None

        # Callbacks
        self.on_aruco_received: Optional[Callable[[int, Any], None]] = None
        self.on_message_received: Optional[Callable[[Data], None]] = None
        self.on_connected: Optional[Callable[[], None]] = None
        self.on_disconnected: Optional[Callable[[], None]] = None

    def set_aruco_callback(self, callback: Callable[[int, Any], None]):
        """Set callback for when ArUco data is received"""
        self.on_aruco_received = callback

    def set_message_callback(self, callback: Callable[[Data], None]):
        """Set callback for any message received"""
        self.on_message_received = callback

    def set_connection_callbacks(
        self,
        on_connected: Callable[[], None] = lambda: None,
        on_disconnected: Callable[[], None] = lambda: None,
    ):
        """Set callbacks for connection events"""
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected

    async def _listen(self):
        """Listen for incoming WebSocket messages"""
        try:
            async with websockets.connect(self.uri) as websocket:
                self.websocket = websocket
                print(f"Connected to WebSocket: {self.uri}")

                # Send bridge identification message immediately after connection
                await websocket.send(json.dumps({"type": "bridge"}))
                print("Sent bridge identification message")

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
                    if self.on_aruco_received:
                        try:
                            raw_data = json.loads(message)
                            data = raw_data.get("data")
                            aruco_id = data.get("id")
                            payload = data.get("data")
                            self.on_aruco_received(aruco_id, payload)
                        except json.JSONDecodeError:
                            print(json.JSONDecodeError)

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

    def send_message(self, message: str):
        """Send a message to the WebSocket server"""
        if self.websocket and self.loop:
            asyncio.run_coroutine_threadsafe(self.websocket.send(message), self.loop)

    def send_json(self, data: dict):
        """Send JSON data to the WebSocket server"""
        self.send_message(json.dumps(data))
