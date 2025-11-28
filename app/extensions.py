from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os, stripe

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY")
STRIPE_CURRENCY = os.environ.get("STRIPE_CURRENCY", "usd")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
