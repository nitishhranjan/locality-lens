import os
from dotenv import load_dotenv
from pathlib import Path

# Get the project root directory (where .env should be)
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Load .env file explicitly from project root
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)
    print(f"✅ Loaded .env from: {ENV_FILE}")
else:
    # Fallback: try default location
    load_dotenv()
    print(f"⚠️ .env file not found at {ENV_FILE}, trying default location")

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Verify API key is loaded
if not GROQ_API_KEY:
    print("⚠️ WARNING: GROQ_API_KEY not found in environment variables")
    print(f"   Check if .env file exists at: {ENV_FILE}")
    print(f"   File exists: {ENV_FILE.exists()}")
else:
    print(f"✅ GROQ_API_KEY loaded (length: {len(GROQ_API_KEY)})")

# App Settings
APP_NAME = "Locality Lens"
DEFAULT_LOCATION = "Indiranagar, Bangalore"
SEARCH_RADIUS = 1000  # meters