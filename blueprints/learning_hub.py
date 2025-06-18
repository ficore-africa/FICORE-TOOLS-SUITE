from flask import Blueprint, render_template, session, request, redirect, url_for, flash, current_app, send_from_directory
from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, HiddenField, FileField
from wtforms.validators import DataRequired, Email, Optional
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_login import current_user
from datetime import datetime
from mailersend_email import send_email, EMAIL_CONFIG
import uuid
import json
import os
from translations import trans as trans_orig
from extensions import mongo
from werkzeug.utils import secure_filename
from models import log_tool_usage
import pymongo
import logging
from flask import g
from session_utils import create_anonymous_session
from app import custom_login_required


learning_hub_bp = Blueprint(
    'learning_hub',
    __name__,
    template_folder='templates/LEARNINGHUB',
    url_prefix='/LEARNINGHUB'
)

# Initialize CSRF protection
csrf = CSRFProtect()

# Define allowed file extensions and upload folder
ALLOWED_EXTENSIONS = {'mp4', 'pdf', 'txt'}
UPLOAD_FOLDER = 'static/uploads'

# Ensure upload folder exists
def init_app(app):
    os.makedirs(app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER), exist_ok=True)
    init_storage(app)
    # Configure logging
    app.logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    app.logger.addHandler(handler)
    # Ensure MongoDB connections are closed on teardown
    @app.teardown_appcontext
    def close_db(error):
        if hasattr(g, 'db'):
            g.db.client.close()
            current_app.logger.info("MongoDB connection closed", extra={'session_id': session.get('sid', 'no-session-id')})

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Courses data with multimedia support
courses_data = {
    "budgeting_101": {
        "id": "budgeting_101",
        "title_en": "Budgeting 101",
        "title_ha": "Tsarin Kudi 101",
        "description_en": "Learn the basics of budgeting.",
        "description_ha": "Koyon asalin tsarin kudi.",
        "title_key": "learning_hub_course_budgeting101_title",
        "desc_key": "learning_hub_course_budgeting101_desc",
        "modules": [
            {
                "id": "module-1",
                "title_key": "learning_hub_module_income_title",
                "lessons": [
                    {
                        "id": "budgeting_101-module-1-lesson-1",
                        "title_key": "learning_hub_lesson_income_sources_title",
                        "content_type": "video",
                        "content_path": "Uploads/budgeting_101_lesson1.mp4",
                        "quiz_id": "quiz-1-1"
                    },
                    {
                        "id": "budgeting_101-module-1-lesson-2",
                        "title_key": "learning_hub_lesson_net_income_title",
                        "content_type": "text",
                        "content_key": "learning_hub_lesson_net_income_content",
                        "quiz_id": None
                    }
                ]
            }
        ]
    },
    "financial_quiz": {
        "id": "financial_quiz",
        "title_en": "Financial Quiz",
        "title_ha": "Jarabawar Kudi",
        "description_en": "Test your financial knowledge.",
        "description_ha": "Gwada ilimin ku na kudi.",
        "title_key": "learning_hub_course_financial_quiz_title",
        "desc_key": "learning_hub_course_financial_quiz_desc",
        "modules": [
            {
                "id": "module-1",
                "title_key": "learning_hub_module_quiz_title",
                "lessons": [
                    {
                        "id": "financial_quiz-module-1-lesson-1",
                        "title_key": "learning_hub_lesson_quiz_intro_title",
                        "content_type": "text",
                        "content_key": "learning_hub_lesson_quiz_intro_content",
                        "quiz_id": "quiz-financial-1"
                    }
                ]
            }
        ]
    },
    "savings_basics": {
        "id": "savings_basics",
        "title_en": "Savings Basics",
        "title_ha": "Asalin Tattara Kudi",
        "description_en": "Understand how to save effectively.",
        "description_ha": "Fahimci yadda ake tattara kudi yadda ya kamata.",
        "title_key": "learning_hub_course_savings_basics_title",
        "desc_key": "learning_hub_course_savings_basics_desc",
        "modules": [
            {
                "id": "module-1",
                "title_key": "learning_hub_module_savings_title",
                "lessons": [
                    {
                        "id": "savings_basics-module-1-lesson-1",
                        "title_key": "learning_hub_lesson_savings_strategies_title",
                        "content_type": "text",
                        "content_key": "learning_hub_lesson_savings_strategies_content",
                        "quiz_id": None
                    }
                ]
            }
        ]
    }
}

quizzes_data = {
    "quiz-1-1": {
        "questions": [
            {
                "question_key": "learning_hub_quiz_income_q1",
                "options_keys": [
                    "learning_hub_quiz_income_opt_salary",
                    "learning_hub_quiz_income_opt_business",
                    "learning_hub_quiz_income_opt_investment",
                    "learning_hub_quiz_income_opt_other"
                ],
                "answer_key": "learning_hub_quiz_income_opt_salary"
            }
        ]
    },
    "quiz-financial-1": {
        "questions": [
            {
                "question_key": "learning_hub_quiz_financial_q1",
                "options_keys": [
                    "learning_hub_quiz_financial_opt_a",
                    "learning_hub_quiz_financial_opt_b",
                    "learning_hub_quiz_financial_opt_c",
                    "learning_hub_quiz_financial_opt_d"
                ],
                "answer_key": "learning_hub_quiz_financial_opt_a"
            }
        ]
    }
}

# Modified translation function with fallback
def trans(key, lang='en', default=None):
    try:
        translation = trans_orig(key, lang=lang)
        return translation if translation else (default or key)
    except Exception as e:
        current_app.logger.warning(f"Translation failed for key='{key}' in lang='{lang}': {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        return default or key

class LearningHubProfileForm(FlaskForm):
    first_name = StringField(validators=[DataRequired()])
    email = StringField(validators=[Optional(), Email()])
    send_email = BooleanField(default=False)
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.first_name.label.text = trans('core_first_name', lang=lang)
        self.email.label.text = trans('core_email', lang=lang)
        self.send_email.label.text = trans('core_send_email', lang=lang)
        self.submit.label.text = trans('core_submit', lang=lang)
        self.first_name.validators[0].message = trans('core_first_name_required', lang=lang)
        if self.email.validators:
            self.email.validators[1].message = trans('core_email_invalid', lang=lang)

class MarkCompleteForm(FlaskForm):
    lesson_id = HiddenField('Lesson ID')
    submit = SubmitField('Mark as Complete')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.submit.label.text = trans('learning_hub_mark_complete', lang=lang)

class QuizForm(FlaskForm):
    submit = SubmitField('Submit Quiz')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.submit.label.text = trans('learning_hub_submit_quiz', lang=lang)

class ContentUploadForm(FlaskForm):
    course_id = StringField('Course ID', validators=[DataRequired()])
    lesson_id = StringField('Lesson ID', validators=[DataRequired()])
    content_type = StringField('Content Type', validators=[DataRequired()])
    file = FileField('Upload File', validators=[DataRequired()])
    submit = SubmitField('Upload')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.submit.label.text = trans('learning_hub_upload', lang=lang)

def get_progress():
    """Retrieve learning progress from MongoDB with caching."""
    try:
        if 'sid' not in session:
            session['sid'] = str(uuid.uuid4())
            session.permanent = True
            session.modified = True
        filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session.get('sid', str(uuid.uuid4()))}
        progress_records = mongo.db.learning_materials.find(filter_kwargs)  # Removed hint
        progress = {}
        for record in progress_records:
            try:
                course_id = record.get('course_id')
                if not course_id:
                    current_app.logger.warning(f"Invalid progress record, missing course_id: {record}", extra={'session_id': session.get('sid', 'no-session-id')})
                    continue
                progress[course_id] = {
                    'lessons_completed': record.get('lessons_completed', []),
                    'quiz_scores': record.get('quiz_scores', {}),
                    'current_lesson': record.get('current_lesson')
                }
            except Exception as e:
                current_app.logger.error(f"Error parsing progress record for course {record.get('course_id', 'unknown')}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        return progress
    except Exception as e:
        current_app.logger.error(f"Error retrieving progress from MongoDB: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_error_loading", default="Error loading content. Please try again.", lang=session.get('lang', 'en')))
        return {}

def save_course_progress(course_id, course_progress):
    """Save course progress to MongoDB with validation."""
    try:
        if 'sid' not in session:
            session['sid'] = str(uuid.uuid4())
            session.permanent = True
            session.modified = True
        if not isinstance(course_id, str) or not isinstance(course_progress, dict):
            current_app.logger.error(f"Invalid course_id or course_progress: course_id={course_id}, course_progress={course_progress}", extra={'session_id': session.get('sid', 'no-session-id')})
            return
        filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
        filter_kwargs['course_id'] = course_id
        update_data = {
            '$set': {
                'user_id': current_user.id if current_user.is_authenticated else None,
                'session_id': session['sid'],
                'course_id': course_id,
                'lessons_completed': course_progress.get('lessons_completed', []),
                'quiz_scores': course_progress.get('quiz_scores', {}),
                'current_lesson': course_progress.get('current_lesson')
            }
        }
        mongo.db.learning_materials.update_one(filter_kwargs, update_data, upsert=True)
        current_app.logger.info(f"Saved progress for course {course_id}", extra={'session_id': session.get('sid')})
    except Exception as e:
        current_app.logger.error(f"Error saving progress to MongoDB for course {course_id}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})

def init_storage(app):
    """Initialize storage with app context and logger."""
    with app.app_context():
        current_app.logger.info("Initializing courses storage.", extra={'session_id': 'no-request-context'})
        try:
            existing_courses = mongo.db.learning_materials.find({'type': 'course'})
            if not existing_courses.count():
                current_app.logger.info("Courses collection is empty. Initializing with default courses.", extra={'session_id': 'no-request-context'})
                default_courses = [
                    {
                        'type': 'course',
                        'id': course['id'],
                        'title_key': course['title_key'],
                        'title_en': course['title_en'],
                        'title_ha': course['title_ha'],
                        'description_en': course['description_en'],
                        'description_ha': course['description_ha'],
                        'is_premium': False
                    } for course in courses_data.values()
                ]
                if default_courses:
                    mongo.db.learning_materials.insert_many(default_courses)
                    current_app.logger.info(f"Initialized courses collection with {len(default_courses)} default courses", extra={'session_id': 'no-request-context'})
        except Exception as e:
            current_app.logger.error(f"Error initializing courses: {str(e)}", extra={'session_id': 'no-request-context'})
            raise

def course_lookup(course_id):
    """Retrieve course by ID with validation."""
    course = courses_data.get(course_id)
    if not course or not isinstance(course, dict) or 'modules' not in course or not isinstance(course['modules'], list):
        current_app.logger.error(f"Invalid course data for course_id {course_id}: {course}", extra={'session_id': session.get('sid', 'no-session-id')})
        return None
    for module in course['modules']:
        if not isinstance(module, dict) or 'lessons' not in module or not isinstance(module['lessons'], list):
            current_app.logger.error(f"Invalid module data in course {course_id}: {module}", extra={'session_id': session.get('sid', 'no-session-id')})
            return None
    return course

def lesson_lookup(course, lesson_id):
    """Retrieve lesson and its module by lesson ID with validation."""
    if not course or not isinstance(course, dict) or 'modules' not in course:
        current_app.logger.error(f"Invalid course data for lesson lookup: {course}", extra={'session_id': session.get('sid', 'no-session-id')})
        return None, None
    for module in course['modules']:
        if not isinstance(module, dict) or 'lessons' not in module:
            current_app.logger.error(f"Invalid module data: {module}", extra={'session_id': session.get('sid', 'no-session-id')})
            continue
        for lesson in module['lessons']:
            if not isinstance(lesson, dict) or 'id' not in lesson:
                current_app.logger.error(f"Invalid lesson data: {lesson}", extra={'session_id': session.get('sid', 'no-session-id')})
                continue
            if lesson['id'] == lesson_id:
                return lesson, module
    current_app.logger.warning(f"Lesson {lesson_id} not found in course", extra={'session_id': session.get('sid', 'no-session-id')})
    return None, None

@learning_hub_bp.route('/courses')
def courses():
    """Display available courses."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    try:
        log_tool_usage(
            mongo=mongo.db,
            tool_name='learning_hub',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='courses_view'
        )
        progress = get_progress()
        if not isinstance(courses_data, dict):
            current_app.logger.error(f"Invalid courses_data type, Path: {request.path}, Type: {type(courses_data)}", extra={'session_id': session.get('sid', 'no-session-id')})
            raise ValueError("courses_data is not a dictionary")
        current_app.logger.info(f"Rendering courses page, Path: {request.path}", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template('LEARNINGHUB/learning_hub_courses.html', courses=courses_data, progress=progress, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error rendering courses page, Path: {request.path}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_error_loading", default="Error loading courses", lang=lang), "danger")
        return render_template('LEARNINGHUB/learning_hub_courses.html', courses={}, progress={}, trans=trans, lang=lang), 500

@learning_hub_bp.route('/courses/<course_id>')
def course_overview(course_id):
    """Display course overview with detailed logging."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    try:
        log_tool_usage(
            mongo=mongo.db,
            tool_name='learning_hub',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='course_overview_view'
        )
        course = course_lookup(course_id)
        if not course:
            current_app.logger.error(f"Course not found, Path: {request.path}, Course ID: {course_id}", extra={'session_id': session.get('sid', 'no-session-id')})
            flash(trans("learning_hub_course_not_found", default="Course not found", lang=lang), "danger")
            return redirect(url_for('learning_hub.courses'))
        progress = get_progress()
        course_progress = progress.get(course_id, {'lessons_completed': [], 'quiz_scores': {}, 'current_lesson': None})
        current_app.logger.info(
            f"Rendering course overview, Path: {request.path}, Course ID: {course_id}, "
            f"Course data: {json.dumps(course, indent=2)}, Progress data: {json.dumps(course_progress, indent=2)}",
            extra={'session_id': session.get('sid', 'no-session-id')}
        )
        return render_template(
            'LEARNINGHUB/learning_hub_course_overview.html',
            course=course,
            progress=course_progress,
            trans=trans,
            lang=lang
        )
    except Exception as e:
        current_app.logger.error(
            f"Error rendering course overview, Path: {request.path}, Course ID: {course_id}: {str(e)}",
            extra={'session_id': session.get('sid', 'no-session-id'), 'course_data': json.dumps(course, default=str)}
        )
        flash(trans("learning_hub_error_loading", default="Error loading course", lang=lang), "danger")
        return redirect(url_for('learning_hub.courses')), 500

@learning_hub_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    """Handle user profile form for first name and email."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    try:
        log_tool_usage(
            mongo=mongo.db,
            tool_name='learning_hub',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='profile_view'
        )
        form_data = session.get('learning_hub_profile', {})
        if current_user.is_authenticated:
            form_data['email'] = form_data.get('email', current_user.email)
            form_data['first_name'] = form_data.get('first_name', current_user.username)
        form = LearningHubProfileForm(data=form_data)
        if request.method == 'POST' and form.validate_on_submit():
            log_tool_usage(
                mongo=mongo.db,
                tool_name='learning_hub',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='profile_submit'
            )
            session['learning_hub_profile'] = {
                'first_name': form.first_name.data,
                'email': form.email.data,
                'send_email': form.send_email.data
            }
            session.permanent = True
            session.modified = True
            current_app.logger.info(f"Profile saved for user {current_user.id if current_user.is_authenticated else 'anonymous'}", extra={'session_id': session.get('sid', 'no-session-id')})
            flash(trans('learning_hub_profile_saved', default='Profile saved successfully', lang=lang), 'success')
            return redirect(url_for('learning_hub.courses'))
        current_app.logger.info(f"Rendering profile page, Path: {request.path}", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template('LEARNINGHUB/learning_hub_profile.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error in profile page: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_error_loading", default="Error loading profile", lang=lang), "danger")
        return render_template('LEARNINGHUB/learning_hub_profile.html', form=form, trans=trans, lang=lang), 500

@learning_hub_bp.route('/courses/<course_id>/lesson/<lesson_id>', methods=['GET', 'POST'])
@custom_login_required
def lesson(course_id, lesson_id):
    """Display or process a lesson with email notification and CSRF protection."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    try:
        log_tool_usage(
            mongo=mongo.db,
            tool_name='learning_hub',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='lesson_view'
        )
        course = course_lookup(course_id)
        if not course:
            current_app.logger.error(f"Course not found, Path: {request.path}, Course ID: {course_id}", extra={'session_id': session.get('sid', 'no-session-id')})
            flash(trans("learning_hub_course_not_found", default="Course not found", lang=lang), "danger")
            return redirect(url_for('learning_hub.courses'))
        lesson, module = lesson_lookup(course, lesson_id)
        if not lesson:
            current_app.logger.error(f"Lesson not found, Path: {request.path}, Lesson ID: {lesson_id}", extra={'session_id': session.get('sid', 'no-session-id')})
            flash(trans("learning_hub_lesson_not_found", default="Lesson not found", lang=lang), "danger")
            return redirect(url_for('learning_hub.course_overview', course_id=course_id))

        form = MarkCompleteForm()
        progress = get_progress()
        if course_id not in progress:
            course_progress = {'lessons_completed': [], 'quiz_scores': {}, 'current_lesson': lesson_id}
            progress[course_id] = course_progress
            save_course_progress(course_id, course_progress)
        else:
            course_progress = progress[course_id]

        # Compute next_lesson_id
        next_lesson_id = None
        found = False
        for m in course['modules']:
            for l in m['lessons']:
                if found and l.get('id'):
                    next_lesson_id = l['id']
                    break
                if l['id'] == lesson_id:
                    found = True
            if next_lesson_id:
                break

        if request.method == 'POST' and form.validate_on_submit():
            log_tool_usage(
                mongo=mongo.db,
                tool_name='learning_hub',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='lesson_complete'
            )
            if form.lesson_id.data == lesson_id and lesson_id not in course_progress['lessons_completed']:
                course_progress['lessons_completed'].append(lesson_id)
                course_progress['current_lesson'] = lesson_id
                save_course_progress(course_id, course_progress)
                flash(trans("learning_hub_lesson_marked", default="Lesson marked as completed", lang=lang), "success")

                # Send email if user has provided details and opted in
                profile = session.get('learning_hub_profile', {})
                if profile.get('send_email') and profile.get('email'):
                    config = EMAIL_CONFIG.get("learning_hub_lesson_completed", {})
                    subject = trans(config.get("subject_key", ""), lang=lang)
                    template = config.get("template", "")
                    try:
                        send_email(
                            app=current_app,
                            logger=current_app.logger,
                            to_email=profile['email'],
                            subject=subject,
                            template_name=template,
                            data={
                                "first_name": profile.get('first_name', ''),
                                "course_title": trans(course['title_key'], lang=lang),
                                "lesson_title": trans(lesson['title_key'], lang=lang),
                                "completed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                "cta_url": url_for('learning_hub.course_overview', course_id=course_id, _external=True),
                                "unsubscribe_url": url_for('learning_hub.unsubscribe', email=profile['email'], _external=True)
                            },
                            lang=lang
                        )
                        current_app.logger.info(f"Sent completion email to {profile['email']} for lesson {lesson_id}", extra={'session_id': session.get('sid', 'no-session-id')})
                    except Exception as e:
                        current_app.logger.error(f"Failed to send email for lesson {lesson_id}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
                        flash(trans("email_send_failed", default="Failed to send email notification", lang=lang), "warning")

                if next_lesson_id:
                    return redirect(url_for('learning_hub.lesson', course_id=course_id, lesson_id=next_lesson_id))
                return redirect(url_for('learning_hub.course_overview', course_id=course_id))
        current_app.logger.info(f"Rendering lesson page, Path: {request.path}, Course ID: {course_id}, Lesson ID: {lesson_id}", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template(
            'LEARNINGHUB/learning_hub_lesson.html',
            course=course,
            lesson=lesson,
            module=module,
            progress=course_progress,
            form=form,
            trans=trans,
            lang=lang,
            next_lesson_id=next_lesson_id
        )
    except Exception as e:
        current_app.logger.error(f"Error in lesson page: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_error_loading", default="Error loading lesson", lang=lang), "danger")
        return redirect(url_for('learning_hub.course_overview', course_id=course_id)), 500

@learning_hub_bp.route('/courses/<course_id>/quiz/<quiz_id>', methods=['GET', 'POST'])
@custom_login_required
def quiz(course_id, quiz_id):
    """Display or process a quiz with CSRF protection."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    try:
        log_tool_usage(
            mongo=mongo.db,
            tool_name='learning_hub',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='quiz_view'
        )
        course = course_lookup(course_id)
        if not course:
            current_app.logger.error(f"Course not found, Path: {request.path}, Course ID: {course_id}", extra={'session_id': session.get('sid', 'no-session-id')})
            flash(trans("learning_hub_course_not_found", default="Course not found", lang=lang), "danger")
            return redirect(url_for('learning_hub.courses'))
        quiz = quizzes_data.get(quiz_id)
        if not quiz or not isinstance(quiz, dict) or 'questions' not in quiz:
            current_app.logger.error(f"Quiz not found or invalid, Path: {request.path}, Quiz ID: {quiz_id}", extra={'session_id': session.get('sid', 'no-session-id')})
            flash(trans("learning_hub_quiz_not_found", default="Quiz not found", lang=lang), "danger")
            return redirect(url_for('learning_hub.course_overview', course_id=course_id))
        progress = get_progress()
        if course_id not in progress:
            course_progress = {'lessons_completed': [], 'quiz_scores': {}, 'current_lesson': None}
            progress[course_id] = course_progress
            save_course_progress(course_id, course_progress)
        else:
            course_progress = progress[course_id]
        form = QuizForm()

        if request.method == 'POST' and form.validate_on_submit():
            log_tool_usage(
                mongo=mongo.db,
                tool_name='learning_hub',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='quiz_submit'
            )
            answers = request.form.to_dict()
            score = 0
            for i, q in enumerate(quiz['questions']):
                user_answer = answers.get(f'q{i}')
                if user_answer and user_answer == trans(q['answer_key'], lang=lang):
                    score += 1
            course_progress['quiz_scores'][quiz_id] = score
            save_course_progress(course_id, course_progress)
            flash(f"{trans('learning_hub_quiz_completed', default='Quiz completed! Score:')} {score}/{len(quiz['questions'])}", "success")
            current_app.logger.info(f"Quiz {quiz_id} completed for course {course_id}, Score: {score}/{len(quiz['questions'])}", extra={'session_id': session.get('sid', 'no-session-id')})
            return redirect(url_for('learning_hub.course_overview', course_id=course_id))
        current_app.logger.info(f"Rendering quiz page, Path: {request.path}, Course ID: {course_id}, Quiz ID: {quiz_id}", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template('LEARNINGHUB/learning_hub_quiz.html', course=course, quiz=quiz, progress=course_progress, form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error processing quiz {quiz_id} for course {course_id}, Path: {request.path}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_error_loading", default="Error loading quiz", lang=lang), "danger")
        return redirect(url_for('learning_hub.course_overview', course_id=course_id)), 500

@learning_hub_bp.route('/dashboard')
@custom_login_required
def dashboard():
    """Display learning hub dashboard."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    try:
        log_tool_usage(
            mongo=mongo.db,
            tool_name='learning_hub',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='dashboard_view'
        )
        progress = get_progress()
        progress_summary = []
        for course_id, course in courses_data.items():
            if not course_lookup(course_id):
                continue
            cp = progress.get(course_id, {'lessons_completed': [], 'current_lesson': None})
            lessons_total = sum(len(m.get('lessons', [])) for m in course.get('modules', []))
            completed = len(cp.get('lessons_completed', []))
            percent = int((completed / lessons_total) * 100) if lessons_total > 0 else 0
            current_lesson_id = cp.get('current_lesson')
            if not current_lesson_id and lessons_total > 0:
                current_lesson_id = course['modules'][0]['lessons'][0]['id'] if course['modules'] and course['modules'][0]['lessons'] else None
            progress_summary.append({
                'course': course,
                'completed': completed,
                'total': lessons_total,
                'percent': percent,
                'current_lesson': current_lesson_id
            })
        current_app.logger.info(f"Rendering dashboard page, Path: {request.path}, Progress Summary: {len(progress_summary)} courses", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template('LEARNINGHUB/learning_hub_dashboard.html', progress_summary=progress_summary, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error rendering dashboard, Path: {request.path}: {str(e)}", exc_info=True, extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_error_loading", default="Error loading dashboard. Please try again.", lang=lang), "danger")
        return render_template('LEARNINGHUB/learning_hub_dashboard.html', progress_summary=[], trans=trans, lang=lang), 500

@learning_hub_bp.route('/unsubscribe/<email>')
def unsubscribe(email):
    """Unsubscribe user from learning hub emails."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    try:
        log_tool_usage(
            mongo=mongo.db,
            tool_name='learning_hub',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='unsubscribe'
        )
        lang = session.get('lang', 'en')
        profile = session.get('learning_hub_profile', {})
        if profile.get('email') == email and profile.get('send_email', False):
            profile['send_email'] = False
            session['learning_hub_profile'] = profile
            session.permanent = True
            session.modified = True
            current_app.logger.info(f"Unsubscribed email {email}", extra={'session_id': session.get('sid', 'no-session-id')})
            flash(trans("learning_hub_unsubscribed_success", default="Successfully unsubscribed from emails", lang=lang), "success")
        else:
            current_app.logger.error(f"Failed to unsubscribe email {email}, Path: {request.path}: No matching profile or already unsubscribed", extra={'session_id': session.get('sid', 'no-session-id')})
            flash(trans("learning_hub_unsubscribe_failed", default="Failed to unsubscribe. Email not found or already unsubscribed.", lang=lang), "danger")
        return redirect(url_for('index'))
    except Exception as e:
        current_app.logger.error(f"Error in unsubscribe, Path: {request.path}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_unsubscribe_error", default="Error processing unsubscribe request", lang=lang), "danger")
        return redirect(url_for('index')), 500

@learning_hub_bp.route('/upload_content', methods=['GET', 'POST'])
@custom_login_required
def upload_content():
    """Handle course content upload with validation."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    try:
        log_tool_usage(
            mongo=mongo.db,
            tool_name='learning_hub',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='upload_content_view'
        )
        form = ContentUploadForm()
        if request.method == 'POST' and form.validate_on_submit():
            log_tool_usage(
                mongo=mongo.db,
                tool_name='learning_hub',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='upload_content_submit'
            )
            file = form.file.data
            course_id = form.course_id.data
            lesson_id = form.lesson_id.data
            content_type = form.content_type.data
            if not course_lookup(course_id):
                flash(trans('learning_hub_course_not_found', default='Course not found', lang=lang), 'danger')
                return redirect(url_for('learning_hub.upload_content'))
            lesson, _ = lesson_lookup(course_lookup(course_id), lesson_id)
            if not lesson:
                flash(trans('learning_hub_lesson_not_found', default='Lesson not found', lang=lang), 'danger')
                return redirect(url_for('learning_hub.upload_content'))
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(current_app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER), filename)
                try:
                    file.save(file_path)
                    # Update courses_data
                    course = course_lookup(course_id)
                    for module in course['modules']:
                        for lesson in module['lessons']:
                            if lesson['id'] == lesson_id:
                                lesson['content_type'] = content_type
                                lesson['content_path'] = f"Uploads/{filename}"
                                break
                    # Store metadata in MongoDB
                    content_metadata = {
                        'type': 'content_metadata',
                        'course_id': course_id,
                        'lesson_id': lesson_id,
                        'content_type': content_type,
                        'content_path': f"Uploads/{filename}",
                        'uploaded_by': current_user.id if current_user.is_authenticated else None,
                        'upload_date': datetime.now()
                    }
                    mongo.db.learning_materials.insert_one(content_metadata)
                    current_app.logger.info(f"Uploaded content for course {course_id}, lesson {lesson_id}: {filename}", extra={'session_id': session.get('sid', 'no-session-id')})
                    flash(trans('learning_hub_content_uploaded', default='Content uploaded successfully', lang=lang), 'success')
                    return redirect(url_for('learning_hub.courses'))
                except Exception as e:
                    current_app.logger.error(f"Error saving content: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
                    flash(trans('learning_hub_error_uploading', default='Error uploading content', lang=lang), 'danger')
            else:
                flash(trans('learning_hub_invalid_file', default='Invalid file type. Allowed: mp4, pdf, txt', lang=lang), 'danger')
        current_app.logger.info(f"Rendering upload content page, Path: {request.path}", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template('LEARNINGHUB/learning_hub_upload.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error in upload content page: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_error_loading", default="Error loading upload page", lang=lang), "danger")
        return render_template('LEARNINGHUB/learning_hub_upload.html', form=form, trans=trans, lang=lang), 500

@learning_hub_bp.route('/static/uploads/<path:filename>')
def serve_uploaded_file(filename):
    """Serve uploaded files securely with caching."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    try:
        log_tool_usage(
            mongo=mongo.db,
            tool_name='learning_hub',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='serve_file'
        )
        response = send_from_directory(current_app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER), filename)
        response.headers['Cache-Control'] = 'public, max-age=31536000'
        current_app.logger.info(f"Served file: {filename}", extra={'session_id': session.get('sid', 'no-session-id')})
        return response
    except Exception as e:
        current_app.logger.error(f"Error serving uploaded file {filename}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_file_not_found", default="File not found", lang=lang), "danger")
        return redirect(url_for('learning_hub.courses')), 404

@learning_hub_bp.errorhandler(404)
def handle_not_found(e):
    """Handle 404 errors with user-friendly message."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    current_app.logger.error(f"404 error on {request.path}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
    flash(trans("learning_hub_not_found", default="The requested page was not found. Please check the URL or return to courses.", lang=lang), "danger")
    return redirect(url_for('learning_hub.courses')), 404

@learning_hub_bp.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files with cache control."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    try:
        log_tool_usage(
            mongo=mongo.db,
            tool_name='learning_hub',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='serve_static_file'
        )
        response = send_from_directory('static', filename)
        response.headers['Cache-Control'] = 'public, max-age=31536000'
        current_app.logger.info(f"Served static file: {filename}", extra={'session_id': session.get('sid', 'no-session-id')})
        return response
    except Exception as e:
        current_app.logger.error(f"Error serving static file {filename}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        return redirect(url_for('learning_hub.courses')), 404

@learning_hub_bp.errorhandler(CSRFError)
def handle_csrf_error(e):
    """Handle CSRF errors with user-friendly message."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    current_app.logger.error(f"CSRF error on {request.path}: {e.description}, Form Data: {request.form}", extra={'session_id': session.get('sid', 'no-session-id')})
    flash(trans("learning_hub_csrf_error", default="Form submission failed due to a missing security token. Please refresh and try again.", lang=lang), "danger")
    return render_template('LEARNINGHUB/400.html', message=trans("learning_hub_csrf_error", default="Form submission failed due to a missing security token. Please refresh and try again.", lang=lang)), 400
