import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# App Settings
APP_NAME = "Locality Lens"
DEFAULT_LOCATION = "Indiranagar, Bangalore"
SEARCH_RADIUS = 1000  # meters
