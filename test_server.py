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
    
    async def send_test_messages(self):
        """Send test ArUco messages periodically"""
        test_messages = [
            {"aruco_id": 1, "data": "red_button"},
            {"aruco_id": 2, "data": "blue_button"},
            {"aruco_ids": [3, 4], "data": {"action": "multi_trigger", "value": 42}},
            {"command": "reset"},
            {"aruco_id": 5, "data": {"complex": "data", "nested": {"key": "value"}}}
        ]
        
        message_index = 0
        while True:
            await asyncio.sleep(10)  # Send a message every 10 seconds
            
            if self.clients:
                message = test_messages[message_index % len(test_messages)]
                json_message = json.dumps(message)
                print(f"📤 Broadcasting test message: {json_message}")
                await self.broadcast(json_message)
                message_index += 1
    
    async def interactive_mode(self):
        """Interactive mode for sending custom messages"""
        print("\n" + "="*50)
        print("INTERACTIVE MODE")
        print("="*50)
        print("Commands:")
        print("  send <aruco_id> <data>  - Send ArUco data")
        print("  multi <id1,id2,id3>     - Send multiple IDs")
        print("  reset                   - Clear all ArUco data")
        print("  clear <aruco_id>        - Clear specific ID")
        print("  quit                    - Exit server")
        print("="*50)
        
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
                        data = parts[2] if len(parts) > 2 else None
                        message = {"aruco_id": aruco_id, "data": data}
                
                elif command.startswith("multi "):
                    ids_str = command.split(" ", 1)[1]
                    ids = [int(id.strip()) for id in ids_str.split(",")]
                    message = {"aruco_ids": ids, "data": "multi_trigger"}
                
                elif command == "reset":
                    message = {"command": "reset"}
                
                elif command.startswith("clear "):
                    aruco_id = int(command.split(" ")[1])
                    message = {"command": "clear", "aruco_id": aruco_id}
                
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
    
    async def start_server(self, auto_send=False, interactive=True):
        """Start the WebSocket server"""
        print(f"🚀 Starting WebSocket server on {self.host}:{self.port}")
        
        # Start the server
        server = await websockets.serve(self.handle_client, self.host, self.port)
        print(f"✅ Server running on ws://{self.host}:{self.port}")
        
        # Start background tasks
        tasks = []
        
        if auto_send:
            tasks.append(asyncio.create_task(self.send_test_messages()))
            print("🤖 Auto-send mode enabled (sends test messages every 10s)")
        
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
    auto_send = "--auto" in sys.argv
    no_interactive = "--no-interactive" in sys.argv
    
    server = TestWebSocketServer()
    
    try:
        asyncio.run(server.start_server(auto_send=auto_send, interactive=not no_interactive))
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
