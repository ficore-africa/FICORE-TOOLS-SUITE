from flask import session
import logging
import uuid
from datetime import datetime

# Set up logging
logger = logging.getLogger('ficore_app')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

def create_anonymous_session():
    """Create a guest session for anonymous access."""
    session['sid'] = str(uuid.uuid4())
    session['is_anonymous'] = True
    session['created_at'] = datetime.utcnow().isoformat()
    logger.info(f"Created anonymous session: {session['sid']}")
