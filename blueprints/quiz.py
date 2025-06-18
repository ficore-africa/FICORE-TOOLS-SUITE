from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email, Optional
from flask_login import current_user
from uuid import uuid4
from datetime import datetime
import json
import logging
from translations import trans
from mailersend_email import send_email, EMAIL_CONFIG
from extensions import mongo
from models import log_tool_usage
from session_utils import create_anonymous_session
from app import custom_login_required

# Configure logging
logger = logging.getLogger('ficore_app')

# Define the quiz blueprint
quiz_bp = Blueprint('quiz', __name__, template_folder='templates/QUIZ', url_prefix='/QUIZ')

# Form for Step 1: Personal Information
class QuizStep1Form(FlaskForm):
    first_name = StringField(validators=[DataRequired()], render_kw={
        'placeholder': trans('core_first_name_placeholder', default='e.g., Muhammad, Bashir, Umar'),
        'title': trans('core_first_name_title', default='Enter your first name to personalize your quiz results')
    })
    email = StringField(validators=[DataRequired(), Email()], render_kw={
        'placeholder': trans('core_email_placeholder', default='e.g., muhammad@example.com'),
        'title': trans('core_email_title', default='Enter your email to receive quiz results')
    })
    lang = SelectField(choices=[('en', 'English'), ('ha', 'Hausa')], default='en', validators=[Optional()])
    send_email = BooleanField(default=False, validators=[Optional()], render_kw={
        'title': trans('core_send_email_title', default='Check to receive an email with your quiz results')
    })
    submit = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.first_name.label.text = trans('core_first_name', default='First Name', lang=lang)
        self.email.label.text = trans('core_email', default='Email', lang=lang)
        self.lang.label.text = trans('core_language', default='Language', lang=lang)
        self.send_email.label.text = trans('core_send_email', default='Send Email', lang=lang)
        self.submit.label.text = trans('quiz_start_quiz', default='Start Quiz', lang=lang)
        self.lang.choices = [
            ('en', trans('core_language_en', default='English', lang=lang)),
            ('ha', trans('core_language_ha', default='Hausa', lang=lang))
        ]

# Form for Step 2a: Questions 1-5
class QuizStep2aForm(FlaskForm):
    question_1 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_1')
    question_2 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_2')
    question_3 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_3')
    question_4 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_4')
    question_5 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_5')
    submit = SubmitField()
    back = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        questions = [
            {'id': 'question_1', 'text_key': 'quiz_track_expenses_label', 'text': 'Do you track your expenses regularly?', 'tooltip_key': 'quiz_track_expenses_tooltip', 'icon': '💰'},
            {'id': 'question_2', 'text_key': 'quiz_save_regularly_label', 'text': 'Do you save a portion of your income regularly?', 'tooltip_key': 'quiz_save_regularly_tooltip', 'icon': '💰'},
            {'id': 'question_3', 'text_key': 'quiz_budget_monthly_label', 'text': 'Do you set a monthly budget?', 'tooltip_key': 'quiz_budget_monthly_tooltip', 'icon': '📝'},
            {'id': 'question_4', 'text_key': 'quiz_emergency_fund_label', 'text': 'Do you have an emergency fund?', 'tooltip_key': 'quiz_emergency_fund_tooltip', 'icon': '🚨'},
            {'id': 'question_5', 'text_key': 'quiz_invest_regularly_label', 'text': 'Do you invest your money regularly?', 'tooltip_key': 'quiz_invest_regularly_tooltip', 'icon': '📈'},
        ]
        for q in questions:
            field = getattr(self, q['id'])
            field.label.text = trans(q['text_key'], default=q['text'], lang=lang)
            field.description = trans(q['tooltip_key'], default='', lang=lang)
            field.choices = [(opt, trans(opt, default=opt, lang=lang)) for opt in ['Yes', 'No']]

        self.submit.label.text = trans('core_continue', default='Continue', lang=lang)
        self.back.label.text = trans('core_back', default='Back', lang=lang)

# Form for Step 2b: Questions 6-10
class QuizStep2bForm(FlaskForm):
    question_6 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_6')
    question_7 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_7')
    question_8 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_8')
    question_9 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_9')
    question_10 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_10')
    submit = SubmitField()
    back = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        questions = [
            {'id': 'question_6', 'text_key': 'quiz_spend_impulse_label', 'text': 'Do you often spend money on impulse?', 'tooltip_key': 'quiz_spend_impulse_tooltip', 'icon': '🛒'},
            {'id': 'question_7', 'text_key': 'quiz_financial_goals_label', 'text': 'Do you set financial goals?', 'tooltip_key': 'quiz_financial_goals_tooltip', 'icon': '🎯'},
            {'id': 'question_8', 'text_key': 'quiz_review_spending_label', 'text': 'Do you review your spending habits regularly?', 'tooltip_key': 'quiz_review_spending_tooltip', 'icon': '🔍'},
            {'id': 'question_9', 'text_key': 'quiz_multiple_income_label', 'text': 'Do you have multiple sources of income?', 'tooltip_key': 'quiz_multiple_income_tooltip', 'icon': '💼'},
            {'id': 'question_10', 'text_key': 'quiz_retirement_plan_label', 'text': 'Do you have a retirement savings plan?', 'tooltip_key': 'quiz_retirement_plan_tooltip', 'icon': '🏖️'},
        ]
        for q in questions:
            field = getattr(self, q['id'])
            field.label.text = trans(q['text_key'], default=q['text'], lang=lang)
            field.description = trans(q['tooltip_key'], default='', lang=lang)
            field.choices = [(opt, trans(opt, default=opt, lang=lang)) for opt in ['Yes', 'No']]

        self.submit.label.text = trans('quiz_see_results', default='See Results', lang=lang)
        self.back.label.text = trans('core_back', default='Back', lang=lang)

# Helper Functions
def calculate_score(answers):
    score = 0
    positive_questions = ['question_1', 'question_2', 'question_3', 'question_4', 'question_5', 'question_7', 'question_8', 'question_9', 'question_10']
    negative_questions = ['question_6']
    for i, answer in enumerate(answers, 1):
        qid = f'question_{i}'
        if qid in positive_questions and answer == 'Yes':
            score += 3
        elif qid in positive_questions and answer == 'No':
            score -= 1
        elif qid in negative_questions and answer == 'No':
            score += 3
        elif qid in negative_questions and answer == 'Yes':
            score -= 1
    return max(0, score)

def assign_personality(score, lang='en'):
    if score >= 21:
        return {
            'name': 'Planner',
            'description': trans('quiz_planner_description', default='You plan your finances meticulously.', lang=lang),
            'insights': [trans('quiz_insight_planner_1', default='You have a strong grasp of financial planning.', lang=lang)],
            'tips': [trans('quiz_tip_planner_1', default='Continue setting long-term goals.', lang=lang)]
        }
    elif score >= 13:
        return {
            'name': 'Saver',
            'description': trans('quiz_saver_description', default='You prioritize saving consistently.', lang=lang),
            'insights': [trans('quiz_insight_saver_1', default='You excel at saving regularly.', lang=lang)],
            'tips': [trans('quiz_tip_saver_1', default='Consider investing to grow your savings.', lang=lang)]
        }
    elif score >= 7:
        return {
            'name': 'Balanced',
            'description': trans('quiz_balanced_description', default='You maintain a balanced financial approach.', lang=lang),
            'insights': [trans('quiz_insight_balanced_1', default='You balance saving and spending well.', lang=lang)],
            'tips': [trans('quiz_tip_balanced_1', default='Try a budgeting app to optimize habits.', lang=lang)]
        }
    elif score >= 3:
        return {
            'name': 'Spender',
            'description': trans('quiz_spender_description', default='You enjoy spending freely.', lang=lang),
            'insights': [trans('quiz_insight_spender_1', default='Spending is a strength, but can be controlled.', lang=lang)],
            'tips': [trans('quiz_tip_spender_1', default='Track expenses to avoid overspending.', lang=lang)]
        }
    else:
        return {
            'name': 'Avoider',
            'description': trans('quiz_avoider_description', default='You avoid financial planning.', lang=lang),
            'insights': [trans('quiz_insight_avoider_1', default='Planning feels challenging but is learnable.', lang=lang)],
            'tips': [trans('quiz_tip_avoider_1', default='Start with a simple monthly budget.', lang=lang)]
        }

def assign_badges(score, lang='en'):
    badges = []
    if score >= 21:
        badges.append({
            'name': trans('badge_financial_guru', default='Financial Guru', lang=lang),
            'color_class': 'bg-primary',
            'description': trans('badge_financial_guru_desc', default='Awarded for excellent financial planning.', lang=lang)
        })
    elif score >= 13:
        badges.append({
            'name': trans('badge_savings_star', default='Savings Star', lang=lang),
            'color_class': 'bg-success',
            'description': trans('badge_savings_star_desc', default='Recognized for consistent saving habits.', lang=lang)
        })
    badges.append({
        'name': trans('badge_first_quiz', default='First Quiz Completed', lang=lang),
        'color_class': 'bg-info',
        'description': trans('badge_first_quiz_desc', default='Completed your first financial quiz.', lang=lang)
    })
    return badges

# Routes
@quiz_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle quiz step 1 form (personal information)."""
    if 'sid' not in session:
        create_anonymous_session()
        logger.debug(f"New anonymous session created with sid: {session['sid']}", extra={'session_id': session['sid']})
    lang = session.get('lang', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    form_data = session.get('quiz_data', {})
    if current_user.is_authenticated:
        form_data['email'] = form_data.get('email', current_user.email)
        form_data['first_name'] = form_data.get('first_name', current_user.username)
    form = QuizStep1Form(lang=lang, data=form_data)
    
    try:
        log_tool_usage(
            mongo,
            tool_name='quiz',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='step1_view'
        )
        if request.method == 'POST':
            log_tool_usage(
                mongo,
                tool_name='quiz',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='step1_submit'
            )
            if form.validate_on_submit():
                session['quiz_data'] = {
                    'first_name': form.first_name.data,
                    'email': form.email.data,
                    'lang': form.lang.data or 'en',
                    'send_email': form.send_email.data
                }
                session['lang'] = form.lang.data or 'en'
                session.modified = True
                logger.info(f"Quiz step 1 validated successfully for session {session['sid']}", extra={'session_id': session['sid']})
                return redirect(url_for('quiz.step2a', course_id=course_id))
            else:
                logger.error(f"Form validation failed in step1: {form.errors}", extra={'session_id': session['sid']})
                flash(trans('quiz_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
        
        return render_template(
            'QUIZ/quiz_step1.html',
            form=form,
            course_id=course_id,
            lang=lang,
            total_steps=3
        )
    except Exception as e:
        logger.error(f"Error in quiz.step1: {str(e)}", extra={'session_id': session['sid']})
        flash(trans('quiz_error_personal_info', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('QUIZ/quiz_step1.html', form=form, course_id=course_id, lang=lang, total_steps=3), 500

@quiz_bp.route('/step2a', methods=['GET', 'POST'])
@custom_login_required
def step2a():
    """Handle quiz step 2a form (questions 1-5)."""
    if 'sid' not in session or 'quiz_data' not in session:
        logger.warning(f"Session expired or missing quiz_data for session {session.get('sid', 'unknown')}", extra={'session_id': session.get('sid', 'unknown')})
        flash(trans('session_expired', default='Session expired. Please start again.', lang=session.get('lang', 'en')), 'danger')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))
    
    lang = session['quiz_data'].get('lang', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    form = QuizStep2aForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    
    # Preprocessed questions for template
    questions = [
        {'id': 'question_1', 'text_key': 'quiz_track_expenses_label', 'text': 'Do you track your expenses regularly?', 'tooltip': 'quiz_track_expenses_tooltip', 'icon': '💰'},
        {'id': 'question_2', 'text_key': 'quiz_save_regularly_label', 'text': 'Do you save a portion of your income regularly?', 'tooltip': 'quiz_save_regularly_tooltip', 'icon': '💰'},
        {'id': 'question_3', 'text_key': 'quiz_budget_monthly_label', 'text': 'Do you set a monthly budget?', 'tooltip': 'quiz_budget_monthly_tooltip', 'icon': '📝'},
        {'id': 'question_4', 'text_key': 'quiz_emergency_fund_label', 'text': 'Do you have an emergency fund?', 'tooltip': 'quiz_emergency_fund_tooltip', 'icon': '🚨'},
        {'id': 'question_5', 'text_key': 'quiz_invest_regularly_label', 'text': 'Do you invest your money regularly?', 'tooltip': 'quiz_invest_regularly_tooltip', 'icon': '📈'},
    ]
    
    try:
        log_tool_usage(
            mongo,
            tool_name='quiz',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='step2a_view'
        )
        if request.method == 'POST':
            log_tool_usage(
                mongo,
                tool_name='quiz',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='step2a_submit'
            )
            if form.back.data:
                return redirect(url_for('quiz.step1', course_id=course_id))
            if form.validate_on_submit():
                session['quiz_data'].update({
                    'question_1': form.question_1.data,
                    'question_2': form.question_2.data,
                    'question_3': form.question_3.data,
                    'question_4': form.question_4.data,
                    'question_5': form.question_5.data,
                })
                session.modified = True
                logger.info(f"Quiz step 2a validated successfully for session {session['sid']}", extra={'session_id': session['sid']})
                return redirect(url_for('quiz.step2b', course_id=course_id))
            else:
                logger.error(f"Form validation failed in step2a: {form.errors}", extra={'session_id': session['sid']})
                flash(trans('quiz_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
        
        # Pre-fill form with session data if available
        for q in questions:
            if q['id'] in session.get('quiz_data', {}):
                getattr(form, q['id']).data = session['quiz_data'][q['id']]
        
        return render_template(
            'QUIZ/quiz_step.html',
            form=form,
            questions=questions,
            course_id=course_id,
            lang=lang,
            step_num=2,
            total_steps=3
        )
    except Exception as e:
        logger.error(f"Error in quiz.step2a: {str(e)}", extra={'session_id': session['sid']})
        flash(trans('quiz_error_questions', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('QUIZ/quiz_step.html', form=form, questions=questions, course_id=course_id, lang=lang, step_num=2, total_steps=3), 500

@quiz_bp.route('/step2b', methods=['GET', 'POST'])
@custom_login_required
def step2b():
    """Handle quiz step 2b form (questions 6-10) and store results in MongoDB."""
    if 'sid' not in session or 'quiz_data' not in session:
        logger.warning(f"Session expired or missing quiz_data for session {session.get('sid', 'unknown')}", extra={'session_id': session.get('sid', 'unknown')})
        flash(trans('session_expired', default='Session expired. Please start again.', lang=session.get('lang', 'en')), 'danger')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))
    
    lang = session['quiz_data'].get('lang', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    form = QuizStep2bForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    
    # Preprocessed questions for template
    questions = [
        {'id': 'question_6', 'text_key': 'quiz_spend_impulse_label', 'text': 'Do you often spend money on impulse?', 'tooltip': 'quiz_spend_impulse_tooltip', 'icon': '🛒'},
        {'id': 'question_7', 'text_key': 'quiz_financial_goals_label', 'text': 'Do you set financial goals?', 'tooltip': 'quiz_financial_goals_tooltip', 'icon': '🎯'},
        {'id': 'question_8', 'text_key': 'quiz_review_spending_label', 'text': 'Do you review your spending habits regularly?', 'tooltip': 'quiz_review_spending_tooltip', 'icon': '🔍'},
        {'id': 'question_9', 'text_key': 'quiz_multiple_income_label', 'text': 'Do you have multiple sources of income?', 'tooltip': 'quiz_multiple_income_tooltip', 'icon': '💼'},
        {'id': 'question_10', 'text_key': 'quiz_retirement_plan_label', 'text': 'Do you have a retirement savings plan?', 'tooltip': 'quiz_retirement_plan_tooltip', 'icon': '🏖️'},
    ]
    
    try:
        log_tool_usage(
            mongo,
            tool_name='quiz',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='step2b_view'
        )
        if request.method == 'POST':
            log_tool_usage(
                mongo,
                tool_name='quiz',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='step2b_submit'
            )
            if form.back.data:
                return redirect(url_for('quiz.step2a', course_id=course_id))
            if form.validate_on_submit():
                session['quiz_data'].update({
                    'question_6': form.question_6.data,
                    'question_7': form.question_7.data,
                    'question_8': form.question_8.data,
                    'question_9': form.question_9.data,
                    'question_10': form.question_10.data,
                })
                session.modified = True
                logger.info(f"Quiz step 2b validated successfully for session {session['sid']}", extra={'session_id': session['sid']})
                
                # Calculate results
                answers = [session['quiz_data'].get(f'question_{i}') for i in range(1, 11)]
                score = calculate_score(answers)
                personality = assign_personality(score, lang)
                badges = assign_badges(score, lang)
                
                # Create and persist quiz result record to MongoDB
                created_at = datetime.utcnow().isoformat()
                quiz_result = {
                    '_id': str(uuid4()),
                    'user_id': current_user.id if current_user.is_authenticated else None,
                    'session_id': session['sid'],
                    'created_at': created_at,
                    'first_name': session['quiz_data'].get('first_name', ''),
                    'email': session['quiz_data'].get('email', ''),
                    'send_email': session['quiz_data'].get('send_email', False),
                    'personality': personality['name'],
                    'score': score,
                    'badges': badges,
                    'insights': personality['insights'],
                    'tips': personality['tips']
                }
                logger.debug(f"Saving quiz result with created_at: {created_at}, type: {type(created_at)}", extra={'session_id': session['sid']})
                mongo.db.quiz_responses.insert_one(quiz_result)
                session['quiz_result_id'] = quiz_result['_id']
                session.modified = True
                logger.info(f"Successfully saved quiz result {quiz_result['_id']} for session {session['sid']}", extra={'session_id': session['sid']})
                
                # Prepare results for display
                results = quiz_result.copy()
                results['created_at'] = datetime.fromisoformat(created_at)  # Convert here to ensure datetime for session and email
                
                # Send email if user opted in
                if session['quiz_data'].get('send_email') and session['quiz_data'].get('email'):
                    try:
                        config = EMAIL_CONFIG["quiz"]
                        subject = trans(config["subject_key"], default='Your Financial Quiz Results', lang=lang)
                        template = config["template"]
                        send_email(
                            app=current_app,
                            logger=current_app.logger,
                            to_email=session['quiz_data']['email'],
                            subject=subject,
                            template_name=template,
                            data={
                                "first_name": results['first_name'],
                                "score": results['score'],
                                "max_score": 30,
                                "personality": results['personality'],
                                "badges": results['badges'],
                                "insights": results['insights'],
                                "tips": results['tips'],
                                "created_at": results['created_at'],
                                "cta_url": url_for('quiz.results', course_id=course_id, _external=True)
                            },
                            lang=lang
                        )
                    except Exception as e:
                        logger.error(f"Failed to send quiz results email: {str(e)}", extra={'session_id': session['sid']})
                        flash(trans("email_send_failed", default="Failed to send email.", lang=lang), "warning")
                
                # Store results in session for immediate display
                session['quiz_results'] = results
                session.modified = True
                
                return redirect(url_for('quiz.results', course_id=course_id))
            else:
                logger.error(f"Form validation failed in step2b: {form.errors}", extra={'session_id': session['sid']})
                flash(trans('quiz_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
        
        # Pre-fill form with session data if available
        for q in questions:
            if q['id'] in session.get('quiz_data', {}):
                getattr(form, q['id']).data = session['quiz_data'][q['id']]
        
        return render_template(
            'QUIZ/quiz_step.html',
            form=form,
            questions=questions,
            course_id=course_id,
            lang=lang,
            step_num=3,
            total_steps=3
        )
    except Exception as e:
        logger.error(f"Error in quiz.step2b: {str(e)}", extra={'session_id': session['sid']})
        flash(trans('quiz_error_questions', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('QUIZ/quiz_step.html', form=form, questions=questions, course_id=course_id, lang=lang, step_num=3, total_steps=3), 500

@quiz_bp.route('/results', methods=['GET'])
@custom_login_required
def results():
    """Display quiz results from MongoDB."""
    if 'sid' not in session:
        create_anonymous_session()
        logger.warning("No session ID found, created new anonymous session", extra={'session_id': session['sid']})
    
    lang = session.get('lang', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    
    try:
        log_tool_usage(
            mongo,
            tool_name='quiz',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='results_view'
        )
        # Try to fetch results from session first
        results = session.get('quiz_results')
        result_source = 'session' if results else 'none'
        
        if not results:
            # Fetch from MongoDB using quiz_result_id or user_id
            if 'quiz_result_id' in session:
                quiz_result = mongo.db.quiz_responses.find_one({'_id': session['quiz_result_id']})
                if quiz_result:
                    results = quiz_result
                    result_source = 'quiz_result_id'
            if not results:
                # Fallback to latest result by user_id
                quiz_result = mongo.db.quiz_responses.find_one(
                    {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']},
                    sort=[('created_at', -1)]
                )
                if quiz_result:
                    results = quiz_result
                    result_source = 'user_id' if current_user.is_authenticated else 'session_id'
            if not results and current_user.is_authenticated and current_user.email:
                # Fallback to email for authenticated users
                quiz_result = mongo.db.quiz_responses.find_one(
                    {'email': current_user.email},
                    sort=[('created_at', -1)]
                )
                if quiz_result:
                    results = quiz_result
                    result_source = 'email'
        
        if not results:
            logger.warning(f"No quiz results found for session {session['sid']}", extra={'session_id': session['sid']})
            flash(trans('quiz_no_results', default='No quiz results found. Please take the quiz again.', lang=lang), 'danger')
            return redirect(url_for('quiz.step1', course_id=course_id))
        
        # Log the source and created_at for debugging
        logger.debug(f"Results fetched from {result_source}, created_at: {results.get('created_at')}, type: {type(results.get('created_at'))}", extra={'session_id': session['sid']})
        
        # Handle created_at conversion
        if isinstance(results.get('created_at'), datetime):
            # Already a datetime, no conversion needed
            pass
        elif isinstance(results.get('created_at'), str):
            try:
                results['created_at'] = datetime.fromisoformat(results['created_at'])
            except (TypeError, ValueError) as e:
                logger.error(f"Failed to parse created_at '{results['created_at']}' in results: {str(e)}", extra={'session_id': session['sid']})
                results['created_at'] = None
        else:
            logger.error(f"Invalid created_at type: {type(results['created_at'])}, value: {results['created_at']}", extra={'session_id': session['sid']})
            results['created_at'] = None
        
        # Clear session data
        session.pop('quiz_data', None)
        session.pop('quiz_results', None)
        session.pop('quiz_result_id', None)
        session.modified = True
        logger.info(f"Displaying quiz results for session {session['sid']} from {result_source}, session data cleared", extra={'session_id': session['sid']})
        
        return render_template(
            'QUIZ/quiz_results.html',
            latest_record=results,
            insights=results.get('insights', []),
            tips=results.get('tips', []),
            course_id=course_id,
            lang=lang,
            max_score=30
        )
    except Exception as e:
        logger.error(f"Error in quiz.results: {str(e)}", extra={'session_id': session['sid']})
        flash(trans('quiz_error_results', default='An error occurred while loading results. Please try again.', lang=lang), 'danger')
        return redirect(url_for('quiz.step1', course_id=course_id)), 500
