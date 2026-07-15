import os
import sys

# Ensure backend directory is in the path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Set mock API key before any service or route is imported
os.environ["GROQ_API_KEY"] = "mock_key_for_testing"
