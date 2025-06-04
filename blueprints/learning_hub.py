from flask import Blueprint, render_template, session, request, redirect, url_for, flash, current_app, send_from_directory
from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, Optional
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_login import current_user
from datetime import datetime
from mailersend_email import send_email, EMAIL_CONFIG
import uuid
import json
from translations import trans
from extensions import db
from models import LearningProgress, Course

learning_hub_bp = Blueprint('learning_hub', __name__)

# Initialize CSRF protection
csrf = CSRFProtect()

# Define courses and quizzes data
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
                        "content_key": "learning_hub_lesson_income_sources_content",
                        "quiz_id": "quiz-1-1"
                    },
                    {
                        "id": "budgeting_101-module-1-lesson-2",
                        "title_key": "learning_hub_lesson_net_income_title",
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

def get_progress():
    """Retrieve learning progress from database."""
    try:
        filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
        progress_records = LearningProgress.query.filter_by(**filter_kwargs).all()
        progress = {}
        for record in progress_records:
            progress[record.course_id] = record.to_dict()
        return progress
    except Exception as e:
        current_app.logger.error(f"Error retrieving progress from database: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        return {}

def save_course_progress(course_id, course_progress):
    """Save course progress to database."""
    try:
        filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
        filter_kwargs['course_id'] = course_id
        progress = LearningProgress.query.filter_by(**filter_kwargs).first()
        if not progress:
            progress = LearningProgress(
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                course_id=course_id
            )
        progress.lessons_completed = json.dumps(course_progress.get('lessons_completed', []))
        progress.quiz_scores = json.dumps(course_progress.get('quiz_scores', {}))
        progress.current_lesson = course_progress.get('current_lesson')
        db.session.add(progress)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving progress to database: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})

def init_storage(app):
    """Initialize storage with app context and logger."""
    with app.app_context():
        current_app.logger.info("Initializing courses storage.", extra={'session_id': 'no-request-context'})
        try:
            courses = Course.query.all()
            if not courses:
                current_app.logger.info("Courses table is empty. Initializing with default courses.", extra={'session_id': 'no-request-context'})
                default_courses = [
                    Course(
                        id=course['id'],
                        title_key=course['title_key'],
                        title_en=course['title_en'],
                        title_ha=course['title_ha'],
                        description_en=course['description_en'],
                        description_ha=course['description_ha'],
                        is_premium=False
                    ) for course in courses_data.values()
                ]
                db.session.bulk_save_objects(default_courses)
                db.session.commit()
                current_app.logger.info(f"Initialized courses table with {len(default_courses)} default courses", extra={'session_id': 'no-request-context'})
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error initializing courses: {str(e)}", extra={'session_id': 'no-request-context'})
            raise

def course_lookup(course_id):
    """Retrieve course by ID."""
    return courses_data.get(course_id)

def lesson_lookup(course, lesson_id):
    """Retrieve lesson and its module by lesson ID."""
    if not course or 'modules' not in course:
        return None, None
    for module in course['modules']:
        for lesson in module.get('lessons', []):
            if lesson.get('id') == lesson_id:
                return lesson, module
    return None, None

@learning_hub_bp.errorhandler(404)
def handle_not_found(e):
    """Handle 404 errors with user-friendly message."""
    lang = session.get('lang', 'en')
    current_app.logger.error(f"404 error on {request.path}: {str(e)}, Session: {session.get('sid', 'no-session-id')}")
    flash(trans("learning_hub_not_found", default="The requested page was not found. Please check the URL or return to courses.", lang=lang), "danger")
    return redirect(url_for('learning_hub.courses'))

@learning_hub_bp.errorhandler(CSRFError)
def handle_csrf_error(e):
    """Handle CSRF errors with user-friendly message."""
    current_app.logger.error(f"CSRF error on {request.path}: {e.description}, Session: {session.get('sid', 'no-session-id')}, Form Data: {request.form}")
    flash(trans("learning_hub_csrf_error", default="Form submission failed due to a missing security token. Please refresh and try again.", lang=session.get('lang', 'en')), "danger")
    return render_template('400.html', message=trans("learning_hub_csrf_error", default="Form submission failed due to a missing security token. Please refresh and try again.", lang=session.get('lang', 'en'))), 400

@learning_hub_bp.route('/courses')
def courses():
    """Display available courses."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    progress = get_progress()
    try:
        if not isinstance(courses_data, dict):
            current_app.logger.error(f"Invalid courses_data type, Path: {request.path}, Type: {type(courses_data)}", extra={'session_id': session.get('sid', 'no-session-id')})
            raise ValueError("courses_data is not a dictionary")
        current_app.logger.info(f"Rendering courses page, Path: {request.path}", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template('learning_hub_courses.html', courses=courses_data, progress=progress, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error rendering courses page, Path: {request.path}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_error_loading", default="Error loading courses", lang=lang), "danger")
        return render_template('learning_hub_courses.html', courses={}, progress={}, trans=trans, lang=lang), 500

@learning_hub_bp.route('/courses/<course_id>')
def course_overview(course_id):
    """Display course overview."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    course = course_lookup(course_id)
    if not course:
        current_app.logger.error(f"Course not found, Path: {request.path}, Course ID: {course_id}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_course_not_found", default="Course not found", lang=lang), "danger")
        return redirect(url_for('learning_hub.courses'))
    progress = get_progress()
    course_progress = progress.get(course_id, {})
    try:
        current_app.logger.info(f"Rendering course overview, Path: {request.path}, Course ID: {course_id}", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template('learning_hub_course_overview.html', course=course, progress=course_progress, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error rendering course overview, Path: {request.path}, Course ID: {course_id}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_error_loading", default="Error loading course", lang=lang), "danger")
        return redirect(url_for('learning_hub.courses'))

@learning_hub_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    """Handle user profile form for first name and email."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    form_data = session.get('learning_hub_profile', {})
    if current_user.is_authenticated:
        form_data['email'] = form_data.get('email', current_user.email)
        form_data['first_name'] = form_data.get('first_name', current_user.username)
    form = LearningHubProfileForm(data=form_data)
    if request.method == 'POST' and form.validate_on_submit():
        session['learning_hub_profile'] = {
            'first_name': form.first_name.data,
            'email': form.email.data,
            'send_email': form.send_email.data
        }
        session.permanent = True
        session.modified = True
        flash(trans('learning_hub_profile_saved', default='Profile saved successfully', lang=lang), 'success')
        return redirect(url_for('learning_hub.courses'))
    current_app.logger.info(f"Rendering profile page, Path: {request.path}", extra={'session_id': session.get('sid', 'no-session-id')})
    return render_template('learning_hub_profile.html', form=form, trans=trans, lang=lang)

@learning_hub_bp.route('/courses/<course_id>/lesson/<lesson_id>', methods=['GET', 'POST'])
def lesson(course_id, lesson_id):
    """Display or process a lesson with email notification and CSRF protection."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
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

    if request.method == 'POST' and form.validate_on_submit():
        if form.lesson_id.data == lesson_id and lesson_id not in course_progress['lessons_completed']:
            course_progress['lessons_completed'].append(lesson_id)
            course_progress['current_lesson'] = lesson_id
            save_course_progress(course_id, course_progress)
            flash(trans("learning_hub_lesson_marked", default="Lesson marked as completed", lang=lang), "success")

            # Send email if user has provided details and opted in
            profile = session.get('learning_hub_profile', {})
            if profile.get('send_email') and profile.get('email'):
                config = EMAIL_CONFIG["learning_hub_lesson_completed"]
                subject = trans(config["subject_key"], lang=lang)
                template = config["template"]
                try:
                    send_email(
                        app=current_app,
                        logger=current_app.logger,
                        to_email=profile['email'],
                        subject=subject,
                        template_name=template,
                        data={
                            "first_name": profile['first_name'],
                            "course_title": trans(course['title_key'], lang=lang),
                            "lesson_title": trans(lesson['title_key'], lang=lang),
                            "completed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            "cta_url": url_for('learning_hub.course_overview', course_id=course_id, _external=True),
                            "unsubscribe_url": url_for('learning_hub.unsubscribe', email=profile['email'], _external=True)
                        },
                        lang=lang
                    )
                except Exception as e:
                    current_app.logger.error(f"Failed to send email: {str(e)}")
                    flash(trans("email_send_failed", lang=lang), "warning")

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
            if next_lesson_id:
                return redirect(url_for('learning_hub.lesson', course_id=course_id, lesson_id=next_lesson_id))
            else:
                return redirect(url_for('learning_hub.course_overview', course_id=course_id))
    current_app.logger.info(f"Rendering lesson page, Path: {request.path}, Course ID: {course_id}, Lesson ID: {lesson_id}", extra={'session_id': session.get('sid', 'no-session-id')})
    return render_template('learning_hub_lesson.html', course=course, lesson=lesson, module=module, progress=course_progress, form=form, trans=trans, lang=lang)

@learning_hub_bp.route('/courses/<course_id>/quiz/<quiz_id>', methods=['GET', 'POST'])
def quiz(course_id, quiz_id):
    """Display or process a quiz with CSRF protection."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    course = course_lookup(course_id)
    if not course:
        current_app.logger.error(f"Course not found, Path: {request.path}, Course ID: {course_id}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_course_not_found", default="Course not found", lang=lang), "danger")
        return redirect(url_for('learning_hub.courses'))
    quiz = quizzes_data.get(quiz_id)
    if not quiz:
        current_app.logger.error(f"Quiz not found, Path: {request.path}, Quiz ID: {quiz_id}", extra={'session_id': session.get('sid', 'no-session-id')})
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

    try:
        if request.method == 'POST' and form.validate_on_submit():
            answers = request.form.to_dict()
            score = 0
            for i, q in enumerate(quiz['questions']):
                user_answer = answers.get(f'q{i}')
                if user_answer and user_answer == trans(q['answer_key'], lang=lang):
                    score += 1
            course_progress['quiz_scores'][quiz_id] = score
            save_course_progress(course_id, course_progress)
            flash(f"{trans('learning_hub_quiz_completed', default='Quiz completed! Score:', lang=lang)} {score}/{len(quiz['questions'])}", "success")
            return redirect(url_for('learning_hub.course_overview', course_id=course_id))
        current_app.logger.info(f"Rendering quiz page, Path: {request.path}, Course ID: {course_id}, Quiz ID: {quiz_id}", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template('learning_hub_quiz.html', course=course, quiz=quiz, progress=course_progress, form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error processing quiz {quiz_id} for course {course_id}, Path: {request.path}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_error_loading", "Error loading quiz", lang=lang), "danger")
        return redirect(url_for('learning_hub.course_overview', course_id=course_id))

@learning_hub_bp.route('/dashboard')
def dashboard():
    """Display learning hub dashboard."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    progress = get_progress()
    progress_summary = []
    try:
        for course_id, course in courses_data.items():
            cp = progress.get(course_id, {})
            lessons_total = sum(len(m.get('lessons', [])) for m in course['modules'])
            completed = len(cp.get('lessons_completed', []))
            percent = int((completed / lessons_total) * 100) if lessons_total > 0 else 0
            progress_summary.append({'course': course, 'completed': completed, 'total': lessons_total, 'percent': percent})
        current_app.logger.info(f"Rendering dashboard page, Path: {request.path}", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template('learning_hub_dashboard.html', progress_summary=progress_summary, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error rendering dashboard, Path: {request.path}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_error_loading", default="Error loading dashboard", lang=lang), "danger")
        return render_template('learning_hub_dashboard.html', progress_summary=[], trans=trans, lang=lang), 500

@learning_hub_bp.route('/unsubscribe/<email>')
def unsubscribe(email):
    """Unsubscribe user from learning hub emails."""
    try:
        lang = session.get('lang', 'en')
        profile = session.get('learning_hub_profile', {})
        if profile.get('email') == email and profile.get('send_email', False):
            profile['send_email'] = False
            session['learning_hub_profile'] = profile
            session.permanent = True
            session.modified = True
            flash(trans("learning_hub_unsubscribed_success", lang=lang), "success")
        else:
            flash(trans("learning_hub_unsubscribe_failed", lang=lang), "danger")
            current_app.logger.error(f"Failed to unsubscribe email {email}, Path: {request.path}: No matching profile or already unsubscribed")
        return redirect(url_for('index'))
    except Exception as e:
        current_app.logger.error(f"Error in unsubscribe, Path: {request.path}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_unsubscribe_error", lang=lang), "danger")
        return redirect(url_for('index'))

@learning_hub_bp.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files with cache control."""
    response = send_from_directory('static', filename)
    response.headers['Cache-Control'] = 'public, max-age=31536000'
    return response
