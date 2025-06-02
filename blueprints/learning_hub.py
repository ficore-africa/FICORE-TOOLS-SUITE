from flask import Blueprint, render_template, session, request, redirect, url_for, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Optional
from datetime import datetime
from mailersend_email import send_email, EMAIL_CONFIG
import uuid

try:
    from app import trans
except ImportError:
    def trans(key, lang=None, **kwargs):
        """Fallback translation function."""
        return key.format(**kwargs)

learning_hub_bp = Blueprint('learning_hub', __name__)

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

# Profile Form Definition
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

def init_storage(app):
    """Initialize storage with app context and logger."""
    with app.app_context():
        current_app.logger.info("Initializing courses storage.", extra={'session_id': 'no-request-context'})
        try:
            courses_storage = app.config['STORAGE_MANAGERS']['courses']
            courses = courses_storage.read_all()
            if not courses:
                current_app.logger.info("Courses storage is empty. Initializing with default courses.", extra={'session_id': 'no-request-context'})
                default_courses = [
                    {
                        'id': course['id'],
                        'title_en': course['title_en'],
                        'title_ha': course['title_ha'],
                        'description_en': course['description_en'],
                        'description_ha': course['description_ha']
                    } for course in courses_data.values()
                ]
                if not courses_storage.create(default_courses):
                    current_app.logger.error("Failed to initialize courses.json with default courses", extra={'session_id': 'no-request-context'})
                    raise RuntimeError("Course initialization failed")
                current_app.logger.info(f"Initialized courses.json with {len(default_courses)} default courses", extra={'session_id': 'no-request-context'})
        except Exception as e:
            current_app.logger.error(f"Error initializing courses: {str(e)}", extra={'session_id': 'no-request-context'})
            raise

def get_progress():
    """Safely retrieve learning progress from session."""
    try:
        return session.setdefault('learning_progress', {})
    except RuntimeError as e:
        current_app.logger.error(f"Error accessing session['learning_progress']: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        return {}

def save_progress():
    """Safely mark session as modified to save progress."""
    try:
        session.modified = True
    except RuntimeError as e:
        current_app.logger.error(f"Error saving session: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})

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
        return render_template('learning_hub_courses.html', courses=courses_data, progress=progress, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error rendering courses page: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
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
        flash(trans("learning_hub_course_not_found", default="Course not found", lang=lang), "danger")
        return redirect(url_for('learning_hub.courses'))
    progress = get_progress().get(course_id, {})
    try:
        return render_template('learning_hub_course_overview.html', course=course, progress=progress, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error rendering course overview for {course_id}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
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
    form = LearningHubProfileForm()
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
    return render_template('learning_hub_profile.html', form=form, trans=trans, lang=lang)

@learning_hub_bp.route('/courses/<course_id>/lesson/<lesson_id>', methods=['GET', 'POST'])
def lesson(course_id, lesson_id):
    """Display or process a lesson with email notification."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    course = course_lookup(course_id)
    if not course:
        flash(trans("learning_hub_course_not_found", default="Course not found", lang=lang), "danger")
        return redirect(url_for('learning_hub.courses'))
    lesson, module = lesson_lookup(course, lesson_id)
    if not lesson:
        flash(trans("learning_hub_lesson_not_found", default="Lesson not found", lang=lang), "danger")
        return redirect(url_for('learning_hub.course_overview', course_id=course_id))

    progress = get_progress()
    course_progress = progress.setdefault(course_id, {'lessons_completed': [], 'quiz_scores': {}, 'current_lesson': lesson_id})
    if request.method == 'POST':
        if lesson_id not in course_progress['lessons_completed']:
            course_progress['lessons_completed'].append(lesson_id)
            course_progress['current_lesson'] = lesson_id
            save_progress()
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
    return render_template('learning_hub_lesson.html', course=course, lesson=lesson, module=module, progress=course_progress, trans=trans, lang=lang)

@learning_hub_bp.route('/courses/<course_id>/quiz/<quiz_id>', methods=['GET', 'POST'])
def quiz(course_id, quiz_id):
    """Display or process a quiz."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    course = course_lookup(course_id)
    if not course:
        flash(trans("learning_hub_course_not_found", default="Course not found", lang=lang), "danger")
        return redirect(url_for('learning_hub.courses'))
    quiz = quizzes_data.get(quiz_id)
    if not quiz:
        flash(trans("learning_hub_quiz_not_found", default="Quiz not found", lang=lang), "danger")
        return redirect(url_for('learning_hub.course_overview', course_id=course_id))
    progress = get_progress()
    course_progress = progress.setdefault(course_id, {'lessons_completed': [], 'quiz_scores': {}, 'current_lesson': None})

    try:
        if request.method == 'POST':
            answers = request.form.to_dict()
            score = 0
            for i, q in enumerate(quiz['questions']):
                user_answer = answers.get(f'q{i}')
                if user_answer and user_answer == trans(q['answer_key'], lang=lang):
                    score += 1
            course_progress['quiz_scores'][quiz_id] = score
            save_progress()
            flash(f"{trans('learning_hub_quiz_completed', default='Quiz completed! Score:', lang=lang)} {score}/{len(quiz['questions'])}", "success")
            return redirect(url_for('learning_hub.course_overview', course_id=course_id))
        return render_template('learning_hub_quiz.html', course=course, quiz=quiz, progress=course_progress, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error processing quiz {quiz_id} for course {course_id}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans("learning_hub_error_loading", default="Error loading quiz", lang=lang), "danger")
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
        return render_template('learning_hub_dashboard.html', progress_summary=progress_summary, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error rendering dashboard: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
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
            current_app.logger.error(f"Failed to unsubscribe email {email}: No matching profile or already unsubscribed")
        return redirect(url_for('index'))
    except Exception as e:
        current_app.logger.exception(f"Error in learning_hub.unsubscribe: {str(e)}")
        flash(trans("learning_hub_unsubscribe_error", lang=lang), "danger")
        return redirect(url_for('index'))