import logging
import os
import sys
from flask import Flask, jsonify, render_template, request, session, redirect, url_for, flash, send_from_directory, has_request_context, g, current_app, make_response
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, CSRFError
from translations import trans
from blueprints.financial_health import financial_health_bp
from blueprints.budget import budget_bp
from blueprints.quiz import quiz_bp
from blueprints.bill import bill_bp
from blueprints.net_worth import net_worth_bp
from blueprints.emergency_fund import emergency_fund_bp
from blueprints.learning_hub import learning_hub_bp
from json_store import JsonStorage
from scheduler_setup import init_scheduler
from jinja2 import environment
import json
import uuid
from datetime import datetime, timedelta

# Constants
SAMPLE_COURSES = [
    {
        'id': 'budgeting_learning_101',
        'title_key': 'learning_hub_course_budgeting101_title',
        'title_en': 'Budgeting Learning 101',
        'title_ha': 'Tsarin Kudi 101',
        'description_en': 'Learn the basics of budgeting.',
        'description_ha': 'Koyon asalin tsarin kudi.',
        'is_premium': False
    },
    {
        'id': 'financial_quiz',
        'title_key': 'learning_hub_course_financial_quiz_title',
        'title_en': 'Financial Quiz',
        'title_ha': 'Jarabawar Kudi',
        'description_en': 'Test your financial knowledge.',
        'description_ha': 'Gwada ilimin ku na kudi.',
        'is_premium': False
    },
    {
        'id': 'savings_basics',
        'title_key': 'learning_hub_course_savings_basics_title',
        'title_en': 'Savings Basics',
        'title_ha': 'Asalin Tattara Kudi',
        'description_en': 'Understand how to save effectively.',
        'description_ha': 'Fahimci yadda ake tattara kudi yadda ya kamata.',
        'is_premium': False
    }
]

# Set up logging
root_logger = logging.getLogger('ficore_app')
root_logger.setLevel(logging.DEBUG)

class SessionFormatter(logging.Formatter):
    def format(self, record):
        record.session_id = getattr(record, 'session_id', 'no_session_id')
        return super().format(record)

formatter = SessionFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s [session: %(session_id)s]')

class SessionAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs['extra'] = kwargs.get('extra', {})
        session_id = kwargs['extra'].get('session_id', 'no-session-id')
        if has_request_context():
            session_id = session.get('sid', 'no-session-id')
        kwargs['extra']['session_id'] = session_id
        return msg, kwargs

logger = SessionAdapter(root_logger, {})

def setup_logging(app):
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    os.makedirs('data', exist_ok=True)
    try:
        file_handler = logging.FileHandler('data/storage.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        logger.info("Logging setup complete with file handler")
    except (PermissionError, OSError) as e:
        logger.warning(f"Failed to set up file logging: {str(e)}")

def setup_session(app):
    session_dir = os.environ.get('SESSION_DIR', 'data/sessions')
    if os.environ.get('RENDER'):
        session_dir = '/tmp/sessions'
    try:
        if os.path.exists(session_dir):
            if not os.path.isdir(session_dir):
                logger.error(f"Session path {session_dir} is not a directory. Removing and recreating.")
                os.remove(session_dir)
                os.makedirs(session_dir)
                logger.info(f"Created session directory at {session_dir}")
            else:
                logger.info(f"Session directory exists at {session_dir}")
        else:
            os.makedirs(session_dir)
            logger.info(f"Created session directory at {session_dir}")
    except (PermissionError, OSError) as e:
        logger.error(f"Failed to create session directory {session_dir}: {str(e)}. Using in-memory sessions.")
        app.config['SESSION_TYPE'] = 'null'
        return
    app.config['SESSION_FILE_DIR'] = session_dir
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    app.config['SESSION_USE_SIGNER'] = True

def init_storage_managers(app):
    storage_managers = {}
    for name, path, init_func in [
        ('financial_health', '/tmp/financial_health.json' if os.environ.get('RENDER') else 'data/financial_health.json', lambda app: JsonStorage(path, logger_instance=app.logger)),
        ('user_progress', '/tmp/user_progress.json' if os.environ.get('RENDER') else 'data/user_progress.json', lambda app: JsonStorage(path, logger_instance=app.logger)),
        ('net_worth', '/tmp/networth.json' if os.environ.get('RENDER') else 'data/networth.json', lambda app: JsonStorage(path, logger_instance=app.logger)),
        ('emergency_fund', '/tmp/emergency_fund.json' if os.environ.get('RENDER') else 'data/emergency_fund.json', lambda app: JsonStorage(path, logger_instance=app.logger)),
        ('courses', '/tmp/courses.json' if os.environ.get('RENDER') else 'data/courses.json', lambda app: JsonStorage(path, logger_instance=app.logger)),
        ('budget', None, lambda app: JsonStorage('/tmp/budget.json' if os.environ.get('RENDER') else 'data/budget.json', logger_instance=app.logger)),
        ('bills', None, lambda app: JsonStorage('/tmp/bills.json' if os.environ.get('RENDER') else 'data/bills.json', logger_instance=app.logger)),
        ('quiz', None, lambda app: JsonStorage('/tmp/quiz.json' if os.environ.get('RENDER') else 'data/quiz.json', logger_instance=app.logger)),
    ]:
        try:
            with app.app_context():
                logger.info(f"Initializing {name} storage")
                storage_managers[name] = init_func(app)
        except Exception as e:
            logger.error(f"Failed to initialize {name} storage: {str(e)}", exc_info=True)
            raise RuntimeError(f"Cannot initialize {name} storage: {str(e)}")
    app.config['STORAGE_MANAGERS'] = storage_managers
    logger.info(f"STORAGE_MANAGERS initialized with keys: {list(storage_managers.keys())}")

def initialize_courses_data(app):
    with app.app_context():
        try:
            courses_storage = app.config['STORAGE_MANAGERS']['courses']
            courses = courses_storage.read_all()
            if not courses:
                logger.info("Courses storage is empty. Initializing with default courses.")
                courses_storage.write([{
                    'id': str(uuid.uuid4()),
                    'session_id': 'initial-load',
                    'timestamp': datetime.utcnow().isoformat() + "Z",
                    'data': course
                } for course in SAMPLE_COURSES])
                courses = courses_storage.read_all()
            # Convert flat courses to expected format if needed
            converted_courses = []
            for course in courses:
                if isinstance(course, dict) and 'data' in course and isinstance(course['data'], dict):
                    converted_courses.append(course)
                elif isinstance(course, dict) and 'id' in course and 'title_key' in course:
                    converted_courses.append({
                        'id': str(uuid.uuid4()),
                        'session_id': 'converted',
                        'timestamp': datetime.utcnow().isoformat() + "Z",
                        'data': course
                    })
                else:
                    logger.warning(f"Skipping invalid course: {course}")
            if converted_courses != courses:
                courses_storage.write(converted_courses)
                logger.info("Converted and rewrote courses to expected format")
            app.config['COURSES'] = converted_courses
        except Exception as e:
            logger.error(f"Error initializing courses: {str(e)}", exc_info=True)
            app.config['COURSES'] = [{
                'id': str(uuid.uuid4()),
                'session_id': 'fallback',
                'timestamp': datetime.utcnow().isoformat() + "Z",
                'data': course
            } for course in SAMPLE_COURSES]

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_fallback-secret-key-for-dev-only-change-me')
    if not os.environ.get('FLASK_SECRET_KEY') and not app.debug:
        logger.critical("FLASK_SECRET_KEY must be set in production")
        raise RuntimeError("FLASK_SECRET_KEY must be set in production")

    logger.info("Starting app creation")
    setup_logging(app)
    setup_session(app)
    app.config['BASE_URL'] = os.environ.get('BASE_URL', 'http://localhost:5000')
    Session(app)
    CSRFProtect(app)

    # Add format_currency filter
    def format_currency(value):
        try:
            return "₦{:,.2f}".format(float(value))
        except (ValueError, TypeError):
            return str(value)  # Fallback to string if formatting fails
    app.jinja_env.filters['format_currency'] = format_currency

    # Initialize storage managers
    with app.app_context():
        logger.info("Starting storage initialization")
        init_storage_managers(app)
        logger.info("Starting scheduler initialization")
        init_scheduler(app)
        logger.info("Starting data initialization")
        initialize_courses_data(app)
        logger.info("Completed data initialization")

    # Register blueprints
    app.register_blueprint(financial_health_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(bill_bp)
    app.register_blueprint(net_worth_bp)
    app.register_blueprint(emergency_fund_bp)
    app.register_blueprint(learning_hub_bp)

    def translate(key, lang='en', logger=logger, **kwargs):
        translation = trans(key, lang=lang, **kwargs)
        if translation == key:
            logger.warning(f"Missing translation for key='{key}' in lang='{lang}'")
        return translation

    app.jinja_env.filters['trans'] = lambda key, **kwargs: translate(
        key,
        lang=kwargs.get('lang', session.get('lang', 'en')),
        logger=g.get('logger', logger) if has_request_context() else logger,
        **{k: v for k, v in kwargs.items() if k != 'lang'}
    )

    @app.template_filter('format_number')
    def format_number(value):
        try:
            if isinstance(value, (int, float)):
                return f"{float(value):,.2f}"
            return str(value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Error formatting number {value}: {str(e)}")
            return str(value)

    @app.before_request
    def setup_session_and_language():
        try:
            if 'sid' not in session:
                session['sid'] = str(uuid.uuid4())
                logger.info(f"New session ID generated: {session['sid']}")
            if 'lang' not in session:
                session['lang'] = request.accept_languages.best_match(['en', 'ha'], 'en')
                logger.info(f"Set default language to {session['lang']}")
            g.logger = logger
            g.logger.info(f"Request started for path: {request.path}")
            if not os.path.exists('data/storage.log'):
                g.logger.warning("data/storage.log not found")
        except Exception as e:
            logger.error(f"Before request error: {str(e)}", exc_info=True)

    @app.context_processor
    def inject_translations():
        lang = session.get('lang', 'en')
        def context_trans(key, **kwargs):
            # Use template-provided lang if available, else fall back to session lang
            used_lang = kwargs.pop('lang', lang)
            return translate(key, lang=used_lang, logger=g.get('logger', logger), **kwargs)
        return {
            'trans': context_trans,
            'current_year': datetime.now().year,
            'LINKEDIN_URL': os.environ.get('LINKEDIN_URL', '#'),
            'TWITTER_URL': os.environ.get('TWITTER_URL', '#'),
            'FACEBOOK_URL': os.environ.get('FACEBOOK_URL', '#'),
            'FEEDBACK_FORM_URL': os.environ.get('FEEDBACK_FORM_URL', '#'),
            'WAITLIST_FORM_URL': os.environ.get('WAITLIST_FORM_URL', '#'),
            'CONSULTANCY_FORM_URL': os.environ.get('CONSULTANCY_FORM_URL', '#'),
            'current_lang': lang
        }

    @app.route('/')
    def index():
        lang = session.get('lang', 'en')
        logger.info("Serving index page")
        try:
            courses = current_app.config['COURSES'] or [{
                'id': str(uuid.uuid4()),
                'session_id': 'fallback',
                'timestamp': datetime.utcnow().isoformat() + "Z",
                'data': course
            } for course in SAMPLE_COURSES]
            logger.info(f"Retrieved {len(courses)} courses")
            title_key_map = {c['id']: c['title_key'] for c in SAMPLE_COURSES}
            processed_courses = []
            for course in courses:
                if isinstance(course, dict) and 'data' in course and isinstance(course['data'], dict):
                    course_data = course['data']
                    processed_courses.append({
                        **course_data,
                        'title_key': title_key_map.get(course_data['id'], f"learning_hub_course_{course_data['id']}_title")
                    })
                else:
                    logger.warning(f"Invalid course format in index: {course}")
                    processed_courses.append(course)
            courses = processed_courses
        except Exception as e:
            logger.error(f"Error retrieving courses: {str(e)}", exc_info=True)
            courses = SAMPLE_COURSES
            flash(translate('learning_hub_error_message', default='An error occurred', lang=lang), 'danger')
        return render_template(
            'index.html',
            t=translate,
            courses=courses,
            lang=lang,
            sample_courses=SAMPLE_COURSES
        )

    @app.route('/set_language/<lang>')
    def set_language(lang):
        valid_langs = ['en', 'ha']
        new_lang = lang if lang in valid_langs else 'en'
        session['lang'] = new_lang
        logger.info(f"Language set to {new_lang}")
        flash(translate('learning_hub_success_language_updated', default='Language updated successfully', lang=new_lang) if new_lang in valid_langs else translate('Invalid language', default='Invalid language', lang=new_lang), 'success' if new_lang in valid_langs else 'danger')
        return redirect(request.referrer or url_for('index'))

    @app.route('/acknowledge_consent', methods=['POST'])
    def acknowledge_consent():
        """
        Handles consent acknowledgement from users.
        Sets a server-side session flag and logs the event.
        
        Returns:
            HTTP 204 No Content on success
            HTTP 400 Bad Request if not a POST request
            HTTP 403 Forbidden if CSRF token is invalid (handled by CSRFProtect)
        """
        if request.method != 'POST':
            logger.warning(f"Invalid method {request.method} for consent acknowledgement")
            return '', 400
        
        # Set consent flag with timestamp
        session['consent_acknowledged'] = {
            'status': True,
            'timestamp': datetime.utcnow().isoformat(),
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent')
        }
        
        # Log the event with session context
        logger.info(f"Consent acknowledged for session {session['sid']} from IP {request.remote_addr}")
        
        # Security headers for the response
        response = make_response('', 204)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        return response

    @app.route('/favicon.ico')
    def favicon():
        logger.info("Serving favicon.ico")
        return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'favicon-32x32.png', mimetype='image/png')

    @app.route('/general_dashboard')
    def general_dashboard():
        lang = session.get('lang', 'en')
        logger.info("Serving general dashboard")
        data = {}
        expected_keys = {
            'score': None,
            'surplus_deficit': None,
            'personality': None,
            'bills': [],
            'net_worth': None,
            'savings_gap': None
        }
        try:
            for tool, storage in current_app.config['STORAGE_MANAGERS'].items():
                try:
                    records = storage.read_all()
                    session_records = [r['data'] for r in records if r.get('data', {}).get('session_id') == session['sid']]
                    if tool == 'courses':
                        data[tool] = session_records
                    else:
                        data[tool] = expected_keys.copy()
                        if session_records:
                            latest_record = session_records[-1]
                            data[tool].update({k: latest_record.get(k, v) for k, v in expected_keys.items()})
                    logger.info(f"Retrieved {len(session_records)} records for {tool}")
                except Exception as e:
                    logger.error(f"Error fetching data for {tool}: {str(e)}", exc_info=True)
                    data[tool] = [] if tool == 'courses' else expected_keys.copy()
            learning_progress = session.get('learning_progress', {})
            data['learning_progress'] = learning_progress if isinstance(learning_progress, dict) else {}
            return render_template('general_dashboard.html', data=data, t=translate, lang=lang)
        except Exception as e:
            logger.error(f"Error in general_dashboard: {str(e)}", exc_info=True)
            flash(translate('global_error_message', default='An error occurred', lang=lang), 'danger')
            return render_template('general_dashboard.html', data={}, t=translate, lang=lang), 500

    @app.route('/logout')
    def logout():
        lang = session.get('lang', 'en')
        logger.info("Logging out user")
        try:
            session_lang = session.get('lang', 'en')
            session.clear()
            session['lang'] = session_lang
            flash(translate('learning_hub_success_logout', default='Successfully logged out', lang=lang), 'success')
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error in logout: {str(e)}", exc_info=True)
            flash(translate('global_error_message', default='An error occurred', lang=lang), 'danger')
            return redirect(url_for('index'))

    @app.route('/about')
    def about():
        lang = session.get('lang', 'en')
        logger.info("Serving about page")
        return render_template('about.html', t=translate, lang=lang)

    @app.route('/health')
    def health():
        logger.info("Health check requested")
        status = {"status": "healthy"}
        try:
            for tool, storage in current_app.config['STORAGE_MANAGERS'].items():
                if not isinstance(storage, JsonStorage):
                    status["status"] = "unhealthy"
                    status["details"] = f"Storage for {tool} is not initialized correctly"
                    return jsonify(status), 500
            if not os.path.exists('data/storage.log'):
                status["status"] = "warning"
                status["details"] = "Log file data/storage.log not found"
                return jsonify(status), 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}", exc_info=True)
            status["status"] = "unhealthy"
            status["details"] = str(e)
            return jsonify(status), 500
        return jsonify(status), 200

    @app.errorhandler(500)
    def internal_error(error):
        lang = session.get('lang', 'en')
        logger.error(f"Server error: {str(error)}", exc_info=True)
        flash(translate('global_error_message', default='An error occurred', lang=lang), 'danger')
        return render_template('500.html', error=str(error), t=translate, lang=lang), 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        lang = session.get('lang', 'en')
        logger.warning(f"CSRF error: {str(error)}")
        flash(translate('csrf_error', default='Invalid CSRF token', lang=lang), 'danger')
        return render_template('error.html', error="Invalid CSRF token", t=translate, lang=lang), 400

    @app.errorhandler(404)
    def page_not_found(error):
        lang = session.get('lang', 'en')
        logger.error(f"404 error: {str(error)}")
        return render_template('404.html', t=translate, lang=lang), 404

    logger.info("App creation completed")
    return app

try:
    app = create_app()
except Exception as e:
    logger.critical(f"Error creating app: {str(e)}", exc_info=True)
    raise

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
