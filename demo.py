#!/usr/bin/env python3
"""
Demo script for WizzyWorks Bridge

This script demonstrates how to send ArUco marker data via WebSocket
to the bridge application.
"""

import asyncio
import websockets
import json
import time

async def send_demo_commands():
    """Send demonstration commands to the bridge"""
    uri = "ws://localhost:8080"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connected to {uri}")
            
            # Demo sequence
            commands = [
                {"message": "Starting demo sequence..."},
                {"aruco_id": 1, "data": "red_action"},
                {"aruco_id": 2, "data": "blue_action"},
                {"aruco_ids": [3, 4, 5], "data": {"type": "multi_action", "value": 100}},
                {"aruco_id": 10, "data": {"complex": {"nested": "data"}, "timestamp": time.time()}},
                {"command": "reset"},
                {"aruco_id": 1, "data": "red_action_again"},
            ]
            
            for i, command in enumerate(commands):
                print(f"\n📤 Sending command {i+1}/{len(commands)}: {json.dumps(command)}")
                await websocket.send(json.dumps(command))
                
                # Wait for response or just pause
                await asyncio.sleep(2)
            
            print("\n✅ Demo sequence completed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Main entry point"""
    print("🎬 WizzyWorks Bridge Demo")
    print("=" * 40)
    print("This demo will send ArUco marker data to the bridge.")
    print("Make sure the test server is running first!")
    print("=" * 40)
    
    try:
        asyncio.run(send_demo_commands())
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted")

if __name__ == "__main__":
    main()
