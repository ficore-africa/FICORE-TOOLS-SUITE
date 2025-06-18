from flask_pymongo import PyMongo
from flask_login import LoginManager
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
import certifi

# MongoDB setup
mongo = PyMongo()

# Other extensions
login_manager = LoginManager()
flask_session = Session()
csrf = CSRFProtect()
