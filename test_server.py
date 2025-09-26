import asyncio
import websockets
import json
import time

class TestWebSocketServer:
    def __init__(self, host="localhost", port=8080):
        self.host = host
        self.port = port
        self.clients = set()
    
    async def handle_client(self, websocket):
        """Handle a new client connection"""
        self.clients.add(websocket)
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        print(f"✅ Client connected: {client_info}")
        
        try:
            # Send welcome message
            welcome = {
                "message": "Connected to WizzyWorks Bridge Test Server",
                "timestamp": time.time()
            }
            await websocket.send(json.dumps(welcome))
            
            # Listen for messages from client
            async for message in websocket:
                print(f"📨 Received from {client_info}: {message}")
                
                # Echo the message back to all clients
                await self.broadcast(f"Echo: {message}")
                
        except websockets.exceptions.ConnectionClosed:
            print(f"❌ Client disconnected: {client_info}")
        finally:
            self.clients.remove(websocket)
    
    async def broadcast(self, message):
        """Broadcast a message to all connected clients"""
        if self.clients:
            await asyncio.gather(
                *[client.send(message) for client in self.clients],
                return_exceptions=True
            )

    async def interactive_mode(self):
        """Interactive mode for sending custom messages"""
        # 1x1 black pixel PNG, base64 encoded
        base64_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

        test_messages = [
            # Simple message
            {"aruco_id": 1, "data": "red_button"},
            # Complex message with new data format and base64 image
            {
                "aruco_id": 2,
                "data": {
                    "id": 2,
                    "data": {
                        "outer_layer": "circle_pulsate",
                        "outer_layer_color": [1.0, 0.2, 0.2],
                        "outer_layer_second_color": [0.8, 0.0, 0.0],
                        "inner_layer": base64_png,
                    },
                },
            },
            # Command to reset aruco targets
            {"command": "reset"},
        ]

        print("\n" + "=" * 50)
        print("INTERACTIVE MODE")
        print("=" * 50)
        print("Commands:")
        print("  send <aruco_id> <data>  - Send ArUco data (data can be JSON)")
        print("  reset                   - Clear all ArUco data")
        print("  clear <aruco_id>        - Clear specific ID")
        print("  test <message_index>    - Send a predefined test message")
        print("  quit                    - Exit server")
        print("=" * 50)

        while True:
            try:
                command = await asyncio.get_event_loop().run_in_executor(
                    None, input, "Enter command: "
                )

                if command.lower() == "quit":
                    break

                message = None

                if command.startswith("send "):
                    parts = command.split(" ", 2)
                    if len(parts) >= 2:
                        aruco_id = int(parts[1])
                        data_str = parts[2] if len(parts) > 2 else "{}"
                        # Try to parse data as JSON, otherwise treat as string
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            data = data_str
                        message = {"aruco_id": aruco_id, "data": data}

                elif command == "reset":
                    message = {"command": "reset"}

                elif command.startswith("clear "):
                    aruco_id = int(command.split(" ")[1])
                    message = {"command": "clear", "aruco_id": aruco_id}
                
                elif command.startswith("test "):
                    try:
                        index = int(command.split(" ")[1])
                        if 0 <= index < len(test_messages):
                            message = test_messages[index]
                        else:
                            print(f"❌ Invalid test message index. Please choose between 0 and {len(test_messages) - 1}.")
                    except (ValueError, IndexError):
                        print("❌ Invalid 'test' command format. Use 'test <index>'.")


                if message:
                    json_message = json.dumps(message)
                    print(f"📤 Sending: {json_message}")
                    await self.broadcast(json_message)
                else:
                    print("❌ Invalid command format")

            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    async def start_server(self, interactive=True):
        """Start the WebSocket server"""
        print(f"🚀 Starting WebSocket server on {self.host}:{self.port}")
        
        # Start the server
        server = await websockets.serve(self.handle_client, self.host, self.port)
        print(f"✅ Server running on ws://{self.host}:{self.port}")
        
        # Start background tasks
        tasks = []
        
        if interactive:
            tasks.append(asyncio.create_task(self.interactive_mode()))
        
        try:
            if tasks:
                await asyncio.gather(*tasks)
            else:
                await server.wait_closed()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down server...")
        finally:
            server.close()
            await server.wait_closed()

def main():
    """Main entry point"""
    import sys
    
    # Parse command line arguments
    no_interactive = "--no-interactive" in sys.argv
    
    server = TestWebSocketServer()
    
    try:
        asyncio.run(server.start_server(interactive=not no_interactive))
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
