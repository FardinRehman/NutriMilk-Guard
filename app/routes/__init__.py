"""
Nutri Milk Guard Routes Package.
"""

from app.routes.dashboard import dashboard_bp
from app.routes.history import history_bp
from app.routes.alerts import alerts_bp
from app.routes.settings import settings_bp
from app.routes.api import api_bp

__all__ = [
    "dashboard_bp",
    "history_bp",
    "alerts_bp",
    "settings_bp",
    "api_bp"
]
