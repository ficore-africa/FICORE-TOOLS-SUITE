from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email, ValidationError
from json_store import JsonStorage
from mailersend_email import send_email, EMAIL_CONFIG
from datetime import datetime
import uuid
import re

try:
    from app import trans
except ImportError:
    def trans(key, lang=None):
        return key

budget_bp = Blueprint('budget', __name__, url_prefix='/budget')

def init_budget_storage(app):
    """Initialize budget_storage within app context."""
    with app.app_context():
        app.logger.info("Initializing budget storage")
        return JsonStorage('/tmp/data/budget.json', logger_instance=app.logger)

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
def step1():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        current_app.logger.info(f"New session ID generated: {session['sid']}")
        # Clear any stale budget data to start fresh
        session.pop('budget_step1', None)
        session.pop('budget_step2', None)
        session.pop('budget_step3', None)
        session.pop('budget_step4', None)
    session.permanent = True
    lang = session.get('lang', 'en')
    form = Step1Form()
    try:
        if request.method == 'POST':
            current_app.logger.info(f"POST request received for step1, session {session['sid']}: Raw form data: {dict(request.form)}")
            if form.validate_on_submit():
                session['budget_step1'] = form.data
                current_app.logger.info(f"Budget step1 form validated successfully for session {session['sid']}: {form.data}")
                return redirect(url_for('budget.step2'))
            else:
                current_app.logger.warning(f"Form validation failed for step1, session {session['sid']}: {form.errors}")
                flash(trans("budget_form_validation_error") or "Please correct the errors in the form", "danger")
        current_app.logger.info(f"Rendering step1 form for session {session['sid']}")
        return render_template('budget_step1.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Unexpected error in budget.step1 for session {session['sid']}: {str(e)}")
        flash(trans("budget_error_personal_info") or "Error processing personal information", "danger")
        return render_template('budget_step1.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        current_app.logger.info(f"New session ID generated: {session['sid']}")
    session.permanent = True
    lang = session.get('lang', 'en')
    form = Step2Form()
    try:
        if 'budget_step1' not in session:
            current_app.logger.warning(f"Missing budget_step1 data for session {session['sid']}")
            flash(trans("budget_missing_previous_steps") or "Please complete previous steps", "danger")
            return redirect(url_for('budget.step1'))
        if request.method == 'POST':
            current_app.logger.info(f"POST request received for step2, session {session['sid']}: Raw form data: {dict(request.form)}")
            if form.validate_on_submit():
                session['budget_step2'] = form.data
                current_app.logger.info(f"Budget step2 form validated successfully for session {session['sid']}: {form.data}")
                return redirect(url_for('budget.step3'))
            else:
                current_app.logger.warning(f"Form validation failed for step2, session {session['sid']}: {form.errors}")
                flash(trans("budget_form_validation_error") or "Please correct the errors in the form", "danger")
        current_app.logger.info(f"Rendering step2 form for session {session['sid']}")
        return render_template('budget_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Unexpected error in budget.step2 for session {session['sid']}: {str(e)}")
        flash(trans("budget_error_income_invalid") or "Error processing income", "danger")
        return render_template('budget_step2.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        current_app.logger.info(f"New session ID generated: {session['sid']}")
    session.permanent = True
    lang = session.get('lang', 'en')
    form = Step3Form()
    try:
        if any(k not in session for k in ['budget_step1', 'budget_step2']):
            current_app.logger.warning(f"Missing budget_step1 or budget_step2 data for session {session['sid']}")
            flash(trans("budget_missing_previous_steps") or "Please complete previous steps", "danger")
            return redirect(url_for('budget.step1'))
        if request.method == 'POST':
            current_app.logger.info(f"POST request received for step3, session {session['sid']}: Raw form data: {dict(request.form)}")
            if form.validate_on_submit():
                session['budget_step3'] = form.data
                current_app.logger.info(f"Budget step3 form validated successfully for session {session['sid']}: {form.data}")
                return redirect(url_for('budget.step4'))
            else:
                current_app.logger.warning(f"Form validation failed for step3, session {session['sid']}: {form.errors}")
                flash(trans("budget_form_validation_error") or "Please correct the errors in the form", "danger")
        current_app.logger.info(f"Rendering step3 form for session {session['sid']}")
        return render_template('budget_step3.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Unexpected error in budget.step3 for session {session['sid']}: {str(e)}")
        flash(trans("budget_error_expenses_invalid") or "Error processing expenses", "danger")
        return render_template('budget_step3.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/step4', methods=['GET', 'POST'])
def step4():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        current_app.logger.info(f"New session ID generated: {session['sid']}")
    session.permanent = True
    lang = session.get('lang', 'en')
    form = Step4Form()

    try:
        session_keys = ['budget_step1', 'budget_step2', 'budget_step3']
        missing_keys = [k for k in session_keys if k not in session]
        current_app.logger.info(f"Session check for {session['sid']}: Missing keys: {missing_keys}")

        if missing_keys:
            current_app.logger.warning(f"Missing session data for session {session['sid']}: {missing_keys}")
            flash(trans("budget_missing_previous_steps") or "Please complete previous steps", "danger")
            return redirect(url_for('budget.step1'))

        if request.method == 'POST':
            current_app.logger.info(f"POST request received for step4, session {session['sid']}: Raw form data: {dict(request.form)}")
            if form.validate_on_submit():
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

                record = {
                    "income": income,
                    "fixed_expenses": expenses,
                    "variable_expenses": 0,
                    "savings_goal": savings_goal,
                    "surplus_deficit": surplus_deficit,
                    "housing": step3_data.get('housing', 0),
                    "food": step3_data.get('food', 0),
                    "transport": step3_data.get('transport', 0),
                    "dependents": step3_data.get('dependents', 0),
                    "miscellaneous": step3_data.get('miscellaneous', 0),
                    "others": step3_data.get('others', 0),
                    "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                try:
                    budget_storage = current_app.config['STORAGE_MANAGERS']['budget']
                    if not budget_storage.is_writable():
                        current_app.logger.error(f"Storage not writable for session {session['sid']}: {budget_storage.filename}")
                        flash(trans("budget_storage_unavailable") or "Storage is currently unavailable", "danger")
                        return render_template('budget_step4.html', form=form, trans=trans, lang=lang)
                    current_app.logger.info(f"Attempting to save budget for session {session['sid']}")
                    budget_storage.append(record, user_email=step1_data.get('email'), session_id=session['sid'])
                    current_app.logger.info(f"Budget saved successfully for session {session['sid']}")
                except Exception as e:
                    current_app.logger.error(f"Budget storage failed for session {session['sid']}: {str(e)}")
                    flash(trans("budget_storage_error") or "Failed to save budget data", "danger")
                    return render_template('budget_step4.html', form=form, trans=trans, lang=lang)

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
                                "first_name":               step1_data.get('first_name', ''),
                                "income":                   income,
                                "expenses":                 expenses,
                                "housing":                  step3_data.get('housing', 0),
                                "food":                     step3_data.get('food', 0),
                                "transport":                step3_data.get('transport', 0),
                                "dependents":               step3_data.get('dependents', 0),
                                "miscellaneous":            step3_data.get('miscellaneous', 0),
                                "others":                   step3_data.get('others', 0),
                                "savings_goal":             savings_goal,
                                "surplus_deficit":          surplus_deficit,
                                "created_at":               datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                "cta_url":                   url_for('budget.dashboard', _external=True)
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
                return render_template('budget_step4.html', form=form, trans=trans, lang=lang)

        current_app.logger.info(f"Rendering step4 form for session {session['sid']}")
        return render_template('budget_step4.html', form=form, trans=trans, lang=lang)

    except Exception as e:
        current_app.logger.exception(f"Unexpected error in budget.step4 for session {session['sid']}: {str(e)}")
        flash(trans("budget_budget_process_error") or "An unexpected error occurred", "danger")
        return render_template('budget_step4.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        current_app.logger.info(f"New session ID generated: {session['sid']}")
    session.permanent = True
    lang = session.get('lang', 'en')
    try:
        current_app.logger.info(f"Request started for path: /budget/dashboard [session: {session['sid']}]")
        
        budget_storage = current_app.config['STORAGE_MANAGERS']['budget']
        user_data = budget_storage.filter_by_session(session['sid'])
        current_app.logger.info(f"Read {len(user_data)} records from budget storage [session: {session['sid']}]")
        current_app.logger.info(f"Filtered {len(user_data)} records for session {session['sid']} in budget storage [session: {session['sid']}]")
        
        budgets = {}
        latest_budget = None
        for record in user_data:
            budget_id = record["id"]
            budget_data = record["data"]
            budget_data['fixed_expenses'] = sum([
                budget_data.get('housing', 0),
                budget_data.get('food', 0),
                budget_data.get('transport', 0),
                budget_data.get('dependents', 0),
                budget_data.get('miscellaneous', 0),
                budget_data.get('others', 0)
            ])
            budget_data['surplus_deficit'] = budget_data.get('income', 0) - budget_data['fixed_expenses']
            budgets[budget_id] = budget_data
            if not latest_budget or budget_data.get('created_at', '') > latest_budget.get('created_at', ''):
                latest_budget = budget_data

        if request.method == 'POST':
            action = request.form.get('action')
            budget_id = request.form.get('budget_id')
            if action == 'delete':
                try:
                    budget_storage.delete_by_id(budget_id)
                    flash(trans("budget_budget_deleted_success") or "Budget deleted successfully", "success")
                    current_app.logger.info(f"Deleted budget ID {budget_id} for session {session['sid']}")
                except Exception as e:
                    current_app.logger.error(f"Failed to delete budget ID {budget_id} for session {session['sid']}: {str(e)}")
                    flash(trans("budget_budget_delete_failed") or "Failed to delete budget", "danger")
                return redirect(url_for('budget.dashboard'))

        categories = {}
        if latest_budget:
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
        if latest_budget:
            if latest_budget.get('surplus_deficit', 0) < 0:
                insights.append(trans("budget_insight_budget_deficit") or "Your budget shows a deficit.")
            elif latest_budget.get('surplus_deficit', 0) > 0:
                insights.append(trans("budget_insight_budget_surplus") or "You have a budget surplus.")
            if latest_budget.get('savings_goal', 0) == 0:
                insights.append(trans("budget_insight_set_savings_goal") or "Consider setting a savings goal.")

        current_app.logger.info(f"Rendering dashboard for session {session['sid']}: {len(budgets)} budgets found")
        return render_template(
            'budget_dashboard.html',
            budgets=budgets,
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
            'budget_dashboard.html',
            budgets={},
            latest_budget={},
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
