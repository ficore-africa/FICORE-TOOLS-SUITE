from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from datetime import datetime  # Ensure datetime is imported

db = SQLAlchemy()
login_manager = LoginManager()
session = Session()
csrf = CSRFProtect()


