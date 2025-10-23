import json
import base64
from io import BytesIO
from PIL import Image
import os
from main import WizzyWorksBridge

def create_dummy_png_base64():
    """Create a small dummy PNG image and return its base64 string."""
    # Create a small 10x10 red square image
    img = Image.new('RGB', (10, 10), color='red')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    image_data = buffer.getvalue()
    base64_string = base64.b64encode(image_data).decode('utf-8')
    return f"data:image/png;base64,{base64_string}"

def test_marker_detection():
    """Test the _handle_marker_detected method with mock data."""
    # Create a WizzyWorksBridge instance (won't connect to real services)
    bridge = WizzyWorksBridge()

    # Mock data with multiple fireworks
    mock_data = {
        "id": 123,
        "fireworks": [
            {
                "outer_layer": "circle",
                "outer_layer_color": [1.0, 0.0, 0.0],  # Red
                "outer_layer_second_color": [0.0, 1.0, 0.0],  # Green
                "outer_layer_specialfx": 0.5,
                "inner_layer": create_dummy_png_base64(),
                "path_speed": 1.0,
                "path_wobble": 0.2,
            },
            {
                "outer_layer": "star",
                "outer_layer_color": [0.0, 0.0, 1.0],  # Blue
                "outer_layer_second_color": [1.0, 1.0, 0.0],  # Yellow
                "outer_layer_specialfx": 0.8,
                "inner_layer": create_dummy_png_base64(),
                "path_speed": 2.0,
                "path_wobble": 0.5,
            }
        ]
    }

    # Mock normalized_x position
    normalized_x = 0.75

    print("🧪 Testing marker detection with mock data...")
    print(f"Mock data: {json.dumps(mock_data, indent=2)}")
    print(f"Normalized X: {normalized_x}")

    # Call the method
    bridge._handle_marker_detected(123, mock_data, normalized_x)

    print("✅ Test completed. Check the output directory for generated files.")

if __name__ == "__main__":
    test_marker_detection()