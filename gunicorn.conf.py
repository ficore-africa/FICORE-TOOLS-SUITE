timeout = 60  # Handle cold starts and scheduler jobs
workers = 1   # Single worker for 512MB RAM
worker_connections = 1000
loglevel = 'info'
errorlog = '-'  # Log to stderr
accesslog = '-' # Log to stderr
bind = '0.0.0.0:10000'  # Match Render’s port
