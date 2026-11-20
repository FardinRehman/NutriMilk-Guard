"""
Nutri Milk Guard - Application Entrypoint.
Usage:
    python run.py
"""

import os
import sys
import logging
from config import Config
from app import create_app

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("nutri_milk_guard")

# Validate configuration on startup
try:
    Config.validate()
except Exception as e:
    logger.critical(f"Configuration Validation Error: {e}")
    sys.exit(1)

# Application instance for WSGI / local development
app = create_app(os.getenv("FLASK_ENV", "development"))

if __name__ == "__main__":
    host = os.getenv("HOST", Config.HOST)
    port = int(os.getenv("PORT", Config.PORT))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

    print("\n" + "=" * 68)
    print("  NUTRI MILK GUARD - IoT MILK QUALITY MONITORING SYSTEM")
    print("  VTU Engineering Project Demonstration Server")
    print("=" * 68)
    print(f"  * Local Web Dashboard: http://{host}:{port}")
    print(f"  * Firebase Project ID: {Config.FIREBASE_PROJECT_ID}")
    print(f"  * Live Database URL:   {Config.FIREBASE_DATABASE_URL}")
    print(f"  * Monitored Path:      {Config.DEFAULT_DB_PATH}")
    print("=" * 68 + "\n")

    # Run Flask server
    # Note: threaded=True is required for concurrent SSE streaming and HTTP requests
    app.run(host=host, port=port, debug=debug, threaded=True)
