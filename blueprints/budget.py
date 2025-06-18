from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email, ValidationError
from flask_login import current_user
from mailersend_email import send_email, EMAIL_CONFIG
from datetime import datetime
import uuid
import re
from translations import trans
from extensions import mongo
from bson import ObjectId
from models import log_tool_usage
from session_utils import create_anonymous_session
from app import custom_login_required

budget_bp = Blueprint(
    'budget',
    __name__,
    template_folder='templates/BUDGET',
    url_prefix='/BUDGET'
)

def strip_commas(value):
    """Strip commas from string values."""
    if isinstance(value, str):
        return value.replace(',', '')
    return value

class Step1Form(FlaskForm):
    first_name = StringField()
    email = StringField()
    send_email = BooleanField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.first_name.label.text = trans('budget_first_name', lang) or 'First Name'
        self.email.label.text = trans('budget_email', lang) or 'Email'
        self.send_email.label.text = trans('budget_send_email', lang) or 'Send Email Summary'
        self.submit.label.text = trans('budget_next', lang) or 'Next'
        self.first_name.validators = [DataRequired(message=trans('budget_first_name_required', lang) or 'First name is required')]
        self.email.validators = [Optional(), Email(message=trans('budget_email_invalid', lang) or 'Invalid email address')]

    def validate_email(self, field):
        """Custom email validation to handle empty strings."""
        if field.data:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, field.data):
                current_app.logger.warning(f"Invalid email format for session {session.get('sid', 'no-session-id')}: {field.data}")
                raise ValidationError(trans('budget_email_invalid', session.get('lang', 'en')) or 'Invalid email address')

class Step2Form(FlaskForm):
    income = FloatField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.income.label.text = trans('budget_monthly_income', lang) or 'Monthly Income'
        self.submit.label.text = trans('budget_next', lang) or 'Next'
        self.income.validators = [
            DataRequired(message=trans('budget_income_required', lang) or 'Income is required'),
            NumberRange(min=0, max=10000000000, message=trans('budget_income_max', lang) or 'Income must be positive and reasonable')
        ]

    def validate_income(self, field):
        """Custom validator to handle comma-separated numbers."""
        if field.data is None:
            return
        try:
            if isinstance(field.data, str):
                field.data = float(strip_commas(field.data))
            current_app.logger.debug(f"Validated income for session {session.get('sid', 'no-session-id')}: {field.data}")
        except ValueError as e:
            current_app.logger.warning(f"Invalid income value for session {session.get('sid', 'no-session-id')}: {field.data}")
            raise ValidationError(trans('budget_income_invalid', session.get('lang', 'en')) or 'Invalid income format')

class Step3Form(FlaskForm):
    housing = FloatField()
    food = FloatField()
    transport = FloatField()
    dependents = FloatField()
    miscellaneous = FloatField()
    others = FloatField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.housing.label.text = trans('budget_housing_rent', lang) or 'Housing/Rent'
        self.food.label.text = trans('budget_food', lang) or 'Food'
        self.transport.label.text = trans('budget_transport', lang) or 'Transport'
        self.dependents.label.text = trans('budget_dependents_support', lang) or 'Dependents Support'
        self.miscellaneous.label.text = trans('budget_miscellaneous', lang) or 'Miscellaneous'
        self.others.label.text = trans('budget_others', lang) or 'Others'
        self.submit.label.text = trans('budget_next', lang) or 'Next'
        for field in [self.housing, self.food, self.transport, self.dependents, self.miscellaneous, self.others]:
            field.validators = [
                DataRequired(message=trans(f'budget_{field.name}_required', lang) or f'{field.label.text} is required'),
                NumberRange(min=0, message=trans('budget_amount_positive', lang) or 'Amount must be positive')
            ]

    def validate(self, extra_validators=None):
        """Custom validation for all float fields."""
        if not super().validate(extra_validators):
            return False
        for field in [self.housing, self.food, self.transport, self.dependents, self.miscellaneous, self.others]:
            try:
                if isinstance(field.data, str):
                    field.data = float(strip_commas(field.data))
                current_app.logger.debug(f"Validated {field.name} for session {session.get('sid', 'no-session-id')}: {field.data}")
            except ValueError as e:
                current_app.logger.warning(f"Invalid {field.name} value for session {session.get('sid', 'no-session-id')}: {field.data}")
                field.errors.append(trans('budget_amount_invalid', session.get('lang', 'en')) or 'Invalid amount format')
                return False
        return True

class Step4Form(FlaskForm):
    savings_goal = FloatField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.savings_goal.label.text = trans('budget_savings_goal', lang) or 'Monthly Savings Goal'
        self.submit.label.text = trans('budget_submit', lang) or 'Calculate Budget'
        self.savings_goal.validators = [
            DataRequired(message=trans('budget_savings_goal_required', lang) or 'Savings goal is required'),
            NumberRange(min=0, message=trans('budget_amount_positive', lang) or 'Amount must be positive')
        ]

    def validate_savings_goal(self, field):
        """Custom validator to handle comma-separated numbers."""
        if field.data is None:
            return
        try:
            if isinstance(field.data, str):
                field.data = float(strip_commas(field.data))
            current_app.logger.debug(f"Validated savings_goal for session {session.get('sid', 'no-session-id')}: {field.data}")
        except ValueError as e:
            current_app.logger.warning(f"Invalid savings_goal value for session {session.get('sid', 'no-session-id')}: {field.data}")
            raise ValidationError(trans('budget_savings_goal_invalid', session.get('lang', 'en')) or 'Invalid savings goal format')

@budget_bp.route('/step1', methods=['GET', 'POST'])
@custom_login_required
def step1():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        current_app.logger.info(f"New session ID generated: {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
        session.pop('budget_step1', None)
        session.pop('budget_step2', None)
        session.pop('budget_step3', None)
        session.pop('budget_step4', None)
    session.permanent = True
    lang = session.get('lang', 'en')
    form_data = session.get('budget_step1', {})
    if current_user.is_authenticated:
        form_data['email'] = form_data.get('email', current_user.email)
        form_data['first_name'] = form_data.get('first_name', current_user.username)
    else:
        form_data['email'] = form_data.get('email', '')
        form_data['first_name'] = form_data.get('first_name', '')
    form = Step1Form(data=form_data)
    try:
        if request.method == 'POST':
            current_app.logger.info(f"POST request received for step1, session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}: Raw form data: {dict(request.form)}")
            if form.validate_on_submit():
                log_tool_usage(
                    mongo,
                    tool_name='budget',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    session_id=session['sid'],
                    action='step1_submit'
                )
                session['budget_step1'] = form.data
                current_app.logger.info(f"Budget step1 form validated successfully for session {session['sid']}: {form.data}")
                return redirect(url_for('budget.step2'))
            else:
                current_app.logger.warning(f"Form validation failed for step1, session {session['sid']}: {form.errors}")
                flash(trans("budget_form_validation_error") or "Please correct the errors in the form", "danger")
        log_tool_usage(
            mongo,
            tool_name='budget',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='step1_view'
        )
        current_app.logger.info(f"Rendering step1 form for session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
        return render_template('BUDGET/budget_step1.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Unexpected error in budget.step1 for session {session['sid']}: {str(e)}")
        flash(trans("budget_error_personal_info") or "Error processing personal information", "danger")
        return render_template('BUDGET/budget_step1.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/step2', methods=['GET', 'POST'])
@custom_login_required
def step2():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        current_app.logger.info(f"New session ID generated: {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
    session.permanent = True
    lang = session.get('lang', 'en')
    form = Step2Form()
    try:
        if 'budget_step1' not in session:
            current_app.logger.warning(f"Missing budget_step1 data for session {session['sid']}")
            flash(trans("budget_missing_previous_steps") or "Please complete previous steps", "danger")
            return redirect(url_for('budget.step1'))
        if request.method == 'POST':
            current_app.logger.info(f"POST request received for step2, session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}: Raw form data: {dict(request.form)}")
            if form.validate_on_submit():
                log_tool_usage(
                    mongo,
                    tool_name='budget',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    session_id=session['sid'],
                    action='step2_submit'
                )
                session['budget_step2'] = form.data
                current_app.logger.info(f"Budget step2 form validated successfully for session {session['sid']}: {form.data}")
                return redirect(url_for('budget.step3'))
            else:
                current_app.logger.warning(f"Form validation failed for step2, session {session['sid']}: {form.errors}")
                flash(trans("budget_form_validation_error") or "Please correct the errors in the form", "danger")
        log_tool_usage(
            mongo,
            tool_name='budget',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='step2_view'
        )
        current_app.logger.info(f"Rendering step2 form for session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
        return render_template('BUDGET/budget_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Unexpected error in budget.step2 for session {session['sid']}: {str(e)}")
        flash(trans("budget_error_income_invalid") or "Error processing income", "danger")
        return render_template('BUDGET/budget_step2.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/step3', methods=['GET', 'POST'])
@custom_login_required
def step3():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        current_app.logger.info(f"New session ID generated: {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
    session.permanent = True
    lang = session.get('lang', 'en')
    form = Step3Form()
    try:
        if any(k not in session for k in ['budget_step1', 'budget_step2']):
            current_app.logger.warning(f"Missing budget_step1 or budget_step2 data for session {session['sid']}")
            flash(trans("budget_missing_previous_steps") or "Please complete previous steps", "danger")
            return redirect(url_for('budget.step1'))
        if request.method == 'POST':
            current_app.logger.info(f"POST request received for step3, session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}: Raw form data: {dict(request.form)}")
            if form.validate_on_submit():
                log_tool_usage(
                    mongo,
                    tool_name='budget',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    session_id=session['sid'],
                    action='step3_submit'
                )
                session['budget_step3'] = form.data
                current_app.logger.info(f"Budget step3 form validated successfully for session {session['sid']}: {form.data}")
                return redirect(url_for('budget.step4'))
            else:
                current_app.logger.warning(f"Form validation failed for step3, session {session['sid']}: {form.errors}")
                flash(trans("budget_form_validation_error") or "Please correct the errors in the form", "danger")
        log_tool_usage(
            mongo,
            tool_name='budget',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='step3_view'
        )
        current_app.logger.info(f"Rendering step3 form for session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
        return render_template('BUDGET/budget_step3.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Unexpected error in budget.step3 for session {session['sid']}: {str(e)}")
        flash(trans("budget_error_expenses_invalid") or "Error processing expenses", "danger")
        return render_template('BUDGET/budget_step3.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/step4', methods=['GET', 'POST'])
@custom_login_required
def step4():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        current_app.logger.info(f"New session ID generated: {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
    session.permanent = True
    lang = session.get('lang', 'en')
    form = Step4Form()

    try:
        session_keys = ['budget_step1', 'budget_step2', 'budget_step3']
        missing_keys = [k for k in session_keys if k not in session]
        current_app.logger.info(f"Session check for {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}: Missing keys: {missing_keys}")

        if missing_keys:
            current_app.logger.warning(f"Missing session data for session {session['sid']}: {missing_keys}")
            flash(trans("budget_missing_previous_steps") or "Please complete previous steps", "danger")
            return redirect(url_for('budget.step1'))

        if request.method == 'POST':
            current_app.logger.info(f"POST request received for step4, session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}: Raw form data: {dict(request.form)}")
            if form.validate_on_submit():
                log_tool_usage(
                    mongo,
                    tool_name='budget',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    session_id=session['sid'],
                    action='step4_submit'
                )
                session['budget_step4'] = form.data
                current_app.logger.info(f"Budget step4 form validated successfully for session {session['sid']}: {form.data}")

                step1_data = session.get('budget_step1', {})
                step2_data = session.get('budget_step2', {})
                step3_data = session.get('budget_step3', {})
                step4_data = session.get('budget_step4', {})

                income = step2_data.get('income', 0)
                expenses = sum([
                    step3_data.get('housing', 0),
                    step3_data.get('food', 0),
                    step3_data.get('transport', 0),
                    step3_data.get('dependents', 0),
                    step3_data.get('miscellaneous', 0),
                    step3_data.get('others', 0)
                ])
                savings_goal = step4_data.get('savings_goal', 0)
                surplus_deficit = income - expenses

                budget_data = {
                    '_id': str(uuid.uuid4()),
                    'user_id': current_user.id if current_user.is_authenticated else None,
                    'session_id': session['sid'],
                    'user_email': step1_data.get('email'),
                    'income': income,
                    'fixed_expenses': expenses,
                    'variable_expenses': 0,
                    'savings_goal': savings_goal,
                    'surplus_deficit': surplus_deficit,
                    'housing': step3_data.get('housing', 0),
                    'food': step3_data.get('food', 0),
                    'transport': step3_data.get('transport', 0),
                    'dependents': step3_data.get('dependents', 0),
                    'miscellaneous': step3_data.get('miscellaneous', 0),
                    'others': step3_data.get('others', 0),
                    'created_at': datetime.utcnow()
                }

                try:
                    mongo.db.budgets.insert_one(budget_data)
                    current_app.logger.info(f"Budget saved successfully to MongoDB for session {session['sid']}")
                except Exception as e:
                    current_app.logger.error(f"Failed to save budget to MongoDB for session {session['sid']}: {str(e)}")
                    flash(trans("budget_storage_error") or "Failed to save budget data", "danger")
                    return render_template('BUDGET/budget_step4.html', form=form, trans=trans, lang=lang)

                email = step1_data.get('email')
                send_email_flag = step1_data.get('send_email', False)
                if send_email_flag and email:
                    try:
                        config = EMAIL_CONFIG["budget"]
                        subject = trans(config["subject_key"], lang=lang)
                        template = config["template"]
                        send_email(
                            app=current_app,
                            logger=current_app.logger,
                            to_email=email,
                            subject=subject,
                            template_name=template,
                            data={
                                "first_name": step1_data.get('first_name', ''),
                                "income": income,
                                "expenses": expenses,
                                "housing": step3_data.get('housing', 0),
                                "food": step3_data.get('food', 0),
                                "transport": step3_data.get('transport', 0),
                                "dependents": step3_data.get('dependents', 0),
                                "miscellaneous": step3_data.get('miscellaneous', 0),
                                "others": step3_data.get('others', 0),
                                "savings_goal": savings_goal,
                                "surplus_deficit": surplus_deficit,
                                "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                "cta_url": url_for('budget.dashboard', _external=True)
                            },
                            lang=lang
                        )
                    except Exception as e:
                        current_app.logger.error(f"Failed to send email: {str(e)}")
                        flash(trans("email_send_failed", lang=lang), "warning")

                session.pop('budget_step1', None)
                session.pop('budget_step2', None)
                session.pop('budget_step3', None)
                session.pop('budget_step4', None)
                current_app.logger.info(f"Session data cleared for session {session['sid']}")

                flash(trans("budget_budget_completed_success") or "Budget created successfully", "success")
                current_app.logger.info(f"Redirecting to dashboard for session {session['sid']}")
                return redirect(url_for('budget.dashboard'))

            else:
                current_app.logger.warning(f"Form validation failed for step4, session {session['sid']}: {form.errors}")
                flash(trans("budget_form_validation_error") or "Please correct the errors in the form", "danger")
                return render_template('BUDGET/budget_step4.html', form=form, trans=trans, lang=lang)

        log_tool_usage(
            mongo,
            tool_name='budget',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='step4_view'
        )
        current_app.logger.info(f"Rendering step4 form for session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
        return render_template('BUDGET/budget_step4.html', form=form, trans=trans, lang=lang)

    except Exception as e:
        current_app.logger.exception(f"Unexpected error in budget.step4 for session {session['sid']}: {str(e)}")
        flash(trans("budget_budget_process_error") or "An unexpected error occurred", "danger")
        return render_template('BUDGET/budget_step4.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/dashboard', methods=['GET', 'POST'])
@custom_login_required
def dashboard():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        current_app.logger.info(f"New session ID generated: {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
    session.permanent = True
    lang = session.get('lang', 'en')
    try:
        current_app.logger.info(f"Request started for path: /budget/dashboard [session: {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}]")
        log_tool_usage(
            mongo,
            tool_name='budget',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='dashboard_view'
        )

        filter_criteria = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
        budgets = list(mongo.db.budgets.find(filter_criteria).sort('created_at', -1))
        current_app.logger.info(f"Read {len(budgets)} records from MongoDB budgets collection [session: {session['sid']}]")

        budgets_dict = {}
        latest_budget = None
        for budget in budgets:
            budget_data = {
                'id': str(budget['_id']),
                'user_id': budget.get('user_id'),
                'session_id': budget.get('session_id'),
                'user_email': budget.get('user_email'),
                'income': budget.get('income', 0.0),
                'fixed_expenses': budget.get('fixed_expenses', 0.0),
                'variable_expenses': budget.get('variable_expenses', 0.0),
                'savings_goal': budget.get('savings_goal', 0.0),
                'surplus_deficit': budget.get('surplus_deficit', 0.0),
                'housing': budget.get('housing', 0.0),
                'food': budget.get('food', 0.0),
                'transport': budget.get('transport', 0.0),
                'dependents': budget.get('dependents', 0.0),
                'miscellaneous': budget.get('miscellaneous', 0.0),
                'others': budget.get('others', 0.0),
                'created_at': budget.get('created_at').strftime('%Y-%m-%dT%H:%M:%S.%fZ') if budget.get('created_at') else ''
            }
            budgets_dict[budget_data['id']] = budget_data
            if not latest_budget or budget.get('created_at') > datetime.strptime(latest_budget['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ'):
                latest_budget = budget_data

        if not latest_budget:
            latest_budget = {
                'income': 0.0,
                'fixed_expenses': 0.0,
                'surplus_deficit': 0.0,
                'savings_goal': 0.0,
                'housing': 0.0,
                'food': 0.0,
                'transport': 0.0,
                'dependents': 0.0,
                'miscellaneous': 0.0,
                'others': 0.0,
                'created_at': ''
            }

        if request.method == 'POST':
            action = request.form.get('action')
            budget_id = request.form.get('budget_id')
            if action == 'delete':
                log_tool_usage(
                    mongo,
                    tool_name='budget',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    session_id=session['sid'],
                    action='delete_budget'
                )
                try:
                    result = mongo.db.budgets.delete_one({'_id': budget_id, **filter_criteria})
                    if result.deleted_count > 0:
                        flash(trans("budget_budget_deleted_success") or "Budget deleted successfully", "success")
                        current_app.logger.info(f"Deleted budget ID {budget_id} for session {session['sid']}")
                    else:
                        flash(trans("budget_budget_not_found") or "Budget not found", "danger")
                except Exception as e:
                    current_app.logger.error(f"Failed to delete budget ID {budget_id} for session {session['sid']}: {str(e)}")
                    flash(trans("budget_budget_delete_failed") or "Failed to delete budget", "danger")
                return redirect(url_for('budget.dashboard'))

        categories = {
            'Housing/Rent': latest_budget.get('housing', 0),
            'Food': latest_budget.get('food', 0),
            'Transport': latest_budget.get('transport', 0),
            'Dependents': latest_budget.get('dependents', 0),
            'Miscellaneous': latest_budget.get('miscellaneous', 0),
            'Others': latest_budget.get('others', 0)
        }

        tips = [
            trans("budget_tip_track_expenses") or "Track your expenses regularly.",
            trans("budget_tip_ajo_savings") or "Consider group savings plans.",
            trans("budget_tip_data_subscriptions") or "Review data subscriptions for savings.",
            trans("budget_tip_plan_dependents") or "Plan for dependents' expenses."
        ]
        insights = []
        if latest_budget.get('income', 0) > 0:
            if latest_budget.get('surplus_deficit', 0) < 0:
                insights.append(trans("budget_insight_budget_deficit") or "Your budget shows a deficit.")
            elif latest_budget.get('surplus_deficit', 0) > 0:
                insights.append(trans("budget_insight_budget_surplus") or "You have a budget surplus.")
            if latest_budget.get('savings_goal', 0) == 0:
                insights.append(trans("budget_insight_set_savings_goal") or "Consider setting a savings goal.")

        current_app.logger.info(f"Rendering dashboard for session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}: {len(budgets_dict)} budgets found")
        return render_template(
            'BUDGET/budget_dashboard.html',
            budgets=budgets_dict,
            latest_budget=latest_budget,
            categories=categories,
            tips=tips,
            insights=insights,
            trans=trans,
            lang=lang
        )
    except Exception as e:
        current_app.logger.exception(f"Unexpected error in budget.dashboard for session {session['sid']}: {str(e)}")
        flash(trans("budget_dashboard_load_error") or "Error loading dashboard", "danger")
        return render_template(
            'BUDGET/budget_dashboard.html',
            budgets={},
            latest_budget={
                'income': 0.0,
                'fixed_expenses': 0.0,
                'surplus_deficit': 0.0,
                'savings_goal': 0.0,
                'housing': 0.0,
                'food': 0.0,
                'transport': 0.0,
                'dependents': 0.0,
                'miscellaneous': 0.0,
                'others': 0.0,
                'created_at': ''
            },
            categories={},
            tips=[
                trans("budget_tip_track_expenses") or "Track your expenses regularly.",
                trans("budget_tip_ajo_savings") or "Consider group savings plans.",
                trans("budget_tip_data_subscriptions") or "Review data subscriptions for savings.",
                trans("budget_tip_plan_dependents") or "Plan for dependents' expenses."
            ],
            insights=[],
            trans=trans,
            lang=lang
        )
