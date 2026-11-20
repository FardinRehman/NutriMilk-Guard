"""
Nutri Milk Guard - Firebase Service Layer.
Manages secure read-only access to Firebase Realtime Database.
Supports both Firebase Admin Python SDK (when service account key is supplied)
and authenticated/secure REST access with automatic reconnection and SSE broadcasting.
"""

import os
import json
import time
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, List
import requests
from config import Config

logger = logging.getLogger(__name__)

# Try importing firebase_admin; handled gracefully if credentials are not configured yet
try:
    import firebase_admin
    from firebase_admin import credentials, db
    FIREBASE_ADMIN_AVAILABLE = True
except ImportError:
    FIREBASE_ADMIN_AVAILABLE = False


class ConnectionStatus:
    CONNECTED = "CONNECTED"
    CONNECTING = "CONNECTING"
    RECONNECTING = "RECONNECTING"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class FirebaseService:
    """
    Singleton service managing communication with Firebase Realtime Database.
    Guarantees read-only access for sensor data to prevent modifying ESP32 state.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(FirebaseService, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, config=None):
        if getattr(self, "_initialized", False):
            return

        self.config = config or Config
        self.database_url = self.config.FIREBASE_DATABASE_URL.rstrip("/")
        self.project_id = self.config.FIREBASE_PROJECT_ID
        self.service_account_path = self.config.GOOGLE_APPLICATION_CREDENTIALS
        self.default_db_path = self.config.DEFAULT_DB_PATH
        self.poll_interval = self.config.UPDATE_POLL_INTERVAL
        self.stale_timeout = self.config.STALE_DATA_TIMEOUT

        # Sanitize Windows TLS environment variables
        for env_var in ("CURL_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
            val = os.environ.get(env_var)
            if val and not os.path.exists(val):
                del os.environ[env_var]

        # State tracking
        self.connection_status = ConnectionStatus.CONNECTING
        self.admin_sdk_initialized = False
        self.last_successful_fetch: Optional[float] = None
        self.last_data_hash: Optional[str] = None
        self.last_payload: Dict[str, Any] = {}
        self.last_error_message: Optional[str] = None
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []

        # Background polling/sync thread control
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._session = requests.Session()

        # Validate URL
        self.config.validate()

        # Initialize connection
        self._init_firebase()
        self._start_background_sync()

        self._initialized = True

    def _init_firebase(self):
        """
        Attempt to initialize Firebase Admin SDK if service account file exists.
        Falls back to REST mode if service account is not yet provided.
        """
        if not FIREBASE_ADMIN_AVAILABLE:
            logger.warning("firebase_admin package not found; using REST protocol.")
            return

        cred_path = self.service_account_path
        if cred_path and os.path.isfile(cred_path):
            try:
                # Check if already initialized to avoid duplicate app errors
                if not firebase_admin._apps:
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred, {
                        'databaseURL': self.database_url
                    })
                self.admin_sdk_initialized = True
                self.connection_status = ConnectionStatus.CONNECTED
                logger.info("Firebase Admin SDK initialized successfully with service account.")
                return
            except Exception as e:
                logger.error(f"Failed to initialize Firebase Admin SDK with {cred_path}: {e}")
                self.last_error_message = f"Admin SDK initialization error: {str(e)}"
        else:
            logger.info(
                f"No service account found at '{cred_path}'. "
                f"Using secure REST mode for read-only database access."
            )

    def fetch_data(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch data at specified path (read-only).
        Enforces read-only behavior; does NOT write to Firebase.
        """
        target_path = (path or self.default_db_path).strip().strip("/")
        
        # 1. Try Firebase Admin SDK if initialized
        if self.admin_sdk_initialized and FIREBASE_ADMIN_AVAILABLE:
            try:
                ref = db.reference(target_path)
                data = ref.get()
                self._update_success_state(data)
                return data if isinstance(data, dict) else {"value": data}
            except Exception as e:
                logger.warning(f"Admin SDK fetch failed for '{target_path}', falling back to REST: {e}")
                self.last_error_message = str(e)

        # 2. Resilient REST fetch
        rest_url = f"{self.database_url}/{target_path}.json"
        try:
            resp = self._session.get(rest_url, timeout=8.0)
            if resp.status_code == 200:
                data = resp.json()
                self._update_success_state(data)
                if data is None:
                    return {}
                return data if isinstance(data, dict) else {"value": data}
            elif resp.status_code == 401 or resp.status_code == 403:
                self.connection_status = ConnectionStatus.ERROR
                self.last_error_message = "Firebase Permission Denied: Database rules require authentication."
                logger.error(self.last_error_message)
                return {}
            else:
                self.connection_status = ConnectionStatus.ERROR
                self.last_error_message = f"Firebase HTTP Error {resp.status_code}: {resp.text}"
                return {}
        except requests.RequestException as e:
            self.connection_status = ConnectionStatus.DISCONNECTED
            self.last_error_message = f"Network connection failed: {str(e)}"
            return {}

    def _update_success_state(self, data: Any):
        """Update telemetry when read succeeds."""
        self.last_successful_fetch = time.time()
        self.connection_status = ConnectionStatus.CONNECTED
        self.last_error_message = None

    def is_stale(self) -> bool:
        """Check if readings have ceased arriving within configured timeout."""
        if self.last_successful_fetch is None:
            return True
        return (time.time() - self.last_successful_fetch) > self.stale_timeout

    def get_connection_info(self) -> Dict[str, Any]:
        """Return diagnostic status information for UI/health checks."""
        stale = self.is_stale()
        status = self.connection_status
        if status == ConnectionStatus.CONNECTED and stale:
            status = ConnectionStatus.STALE

        last_fetch_iso = None
        if self.last_successful_fetch:
            last_fetch_iso = datetime.fromtimestamp(
                self.last_successful_fetch, tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S UTC")

        return {
            "status": status,
            "is_connected": status == ConnectionStatus.CONNECTED,
            "is_stale": stale,
            "admin_sdk_active": self.admin_sdk_initialized,
            "mode": "Firebase Admin SDK" if self.admin_sdk_initialized else "Secure REST Stream",
            "project_id": self.project_id,
            "database_url": self.database_url,
            "target_path": self.default_db_path,
            "last_successful_fetch": last_fetch_iso,
            "seconds_since_last_fetch": round(time.time() - (self.last_successful_fetch or 0), 1) if self.last_successful_fetch else None,
            "stale_timeout_seconds": self.stale_timeout,
            "error_message": self.last_error_message
        }

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe a callback to be notified on incoming updates."""
        if callback not in self.listeners:
            self.listeners.append(callback)

    def unsubscribe(self, callback: Callable[[Dict[str, Any]], None]):
        """Unsubscribe a callback."""
        if callback in self.listeners:
            self.listeners.remove(callback)

    def _broadcast(self, payload: Dict[str, Any]):
        """Broadcast new payload to all registered callbacks."""
        for listener in list(self.listeners):
            try:
                listener(payload)
            except Exception as e:
                logger.error(f"Error in broadcast listener callback: {e}")

    def _start_background_sync(self):
        """Start worker thread to monitor updates and feed SSE clients."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="FirebaseMonitorThread"
        )
        self._monitor_thread.start()

    def _monitor_loop(self):
        """Worker loop polling Firebase at configured interval and detecting changes."""
        logger.info(f"Firebase monitor worker started. Target path: {self.default_db_path}")
        while not self._stop_event.is_set():
            try:
                raw_data = self.fetch_data()
                data_hash = json.dumps(raw_data, sort_keys=True)
                
                # Check for updates or periodic refresh
                self.last_payload = raw_data
                self.last_data_hash = data_hash
                
                # Broadcast payload to subscribers
                self._broadcast(raw_data)
            except Exception as e:
                logger.error(f"Error in Firebase sync loop: {e}")
                self.connection_status = ConnectionStatus.ERROR
                self.last_error_message = str(e)
            
            # Sleep with interruptible wait
            self._stop_event.wait(self.poll_interval)

    def stop(self):
        """Stop background worker cleanly."""
        self._stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
