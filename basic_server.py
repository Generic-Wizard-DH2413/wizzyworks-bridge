import asyncio
import websockets
import json

async def handle_client(websocket):
    print(f"Client connected: {websocket.remote_address}")
    
    try:
        # Send initial ArUco data
        await websocket.send(json.dumps({"aruco_id": 1, "data": "test_red"}))
        await asyncio.sleep(1)
        await websocket.send(json.dumps({"aruco_id": 2, "data": "test_blue"}))
        
        # Keep connection alive and listen for responses
        async for message in websocket:
            print(f"Received: {message}")
            
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")

async def main():
    print("Starting WebSocket server on localhost:8080")
    server = await websockets.serve(handle_client, "localhost", 8080)
    print("Server ready!")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
