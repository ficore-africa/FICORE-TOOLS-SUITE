from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email, ValidationError
from flask_login import current_user
from datetime import datetime
import uuid
import json
from mailersend_email import send_email, EMAIL_CONFIG
from translations import trans
from extensions import mongo
from models import log_tool_usage
from session_utils import create_anonymous_session
from app import custom_login_required

# Blueprint setup
financial_health_bp = Blueprint(
    'financial_health',
    __name__,
    template_folder='templates/HEALTHSCORE',
    url_prefix='/HEALTHSCORE'
)

# MongoDB client setup using Flask-PyMongo
def get_mongo_collection():
    return mongo.db['financial_health_scores']

class Step1Form(FlaskForm):
    first_name = StringField()
    email = StringField()
    user_type = SelectField()
    send_email = BooleanField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.first_name.label.text = trans('financial_health_first_name', lang=lang)
        self.email.label.text = trans('financial_health_email', lang=lang)
        self.user_type.label.text = trans('financial_health_user_type', lang=lang)
        self.send_email.label.text = trans('financial_health_send_email', lang=lang)
        self.submit.label.text = trans('financial_health_next', lang=lang)
        self.first_name.validators = [DataRequired(message=trans('financial_health_first_name_required', lang=lang))]
        self.email.validators = [Optional(), Email(message=trans('financial_health_email_invalid', lang=lang))]
        self.user_type.choices = [
            ('individual', trans('financial_health_user_type_individual', lang=lang)),
            ('business', trans('financial_health_user_type_business', lang=lang))
        ]

class Step2Form(FlaskForm):
    income = FloatField()
    expenses = FloatField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.income.label.text = trans('financial_health_monthly_income', lang=lang)
        self.expenses.label.text = trans('financial_health_monthly_expenses', lang=lang)
        self.submit.label.text = trans('financial_health_next', lang=lang)
        self.income.validators = [
            DataRequired(message=trans('financial_health_income_required', lang=lang)),
            NumberRange(min=0, max=10000000000, message=trans('financial_health_income_max', lang=lang))
        ]
        self.expenses.validators = [
            DataRequired(message=trans('financial_health_expenses_required', lang=lang)),
            NumberRange(min=0, max=10000000000, message=trans('financial_health_expenses_max', lang=lang))
        ]

    def validate_income(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data)
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid income input: {field.data}")
                raise ValidationError(trans('financial_health_income_invalid', lang=session.get('lang', 'en')))

    def validate_expenses(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data)
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid expenses input: {field.data}")
                raise ValidationError(trans('financial_health_expenses_invalid', lang=session.get('lang', 'en')))

class Step3Form(FlaskForm):
    debt = FloatField()
    interest_rate = FloatField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.debt.label.text = trans('financial_health_total_debt', lang=lang)
        self.interest_rate.label.text = trans('financial_health_average_interest_rate', lang=lang)
        self.submit.label.text = trans('financial_health_submit', lang=lang)
        self.debt.validators = [
            Optional(),
            NumberRange(min=0, max=10000000000, message=trans('financial_health_debt_max', lang=lang))
        ]
        self.interest_rate.validators = [
            Optional(),
            NumberRange(min=0, message=trans('financial_health_interest_rate_positive', lang=lang))
        ]

    def validate_debt(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data) if cleaned_data else None
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid debt input: {field.data}")
                raise ValidationError(trans('financial_health_debt_invalid', lang=session.get('lang', 'en')))

    def validate_interest_rate(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data) if cleaned_data else None
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid interest rate input: {field.data}")
                raise ValidationError(trans('financial_health_interest_rate_invalid', lang=session.get('lang', 'en')))

@financial_health_bp.route('/step1', methods=['GET', 'POST'])
@custom_login_required
def step1():
    """Handle financial health step 1 form (personal info)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')
    form_data = session.get('health_step1', {})
    if current_user.is_authenticated:
        form_data['email'] = form_data.get('email', current_user.email)
        form_data['first_name'] = form_data.get('first_name', current_user.username)
    else:
        form_data['email'] = form_data.get('email', '')
        form_data['first_name'] = form_data.get('first_name', '')
    form = Step1Form(data=form_data)
    current_app.logger.info(f"Starting step1 for session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
    log_tool_usage(
        mongo,
        tool_name='financial_health',
        user_id=current_user.id if current_user.is_authenticated else None,
        session_id=session['sid'],
        action='step1_view'
    )
    try:
        if request.method == 'POST':
            if not form.validate_on_submit():
                current_app.logger.error(f"Form validation failed: {form.errors}")
                flash(trans("financial_health_form_errors", lang=lang), "danger")
                return render_template('HEALTHSCORE/health_score_step1.html', form=form, trans=trans, lang=lang)

            form_data = form.data.copy()
            if form_data.get('email') and not isinstance(form_data['email'], str):
                current_app.logger.error(f"Invalid email type: {type(form_data['email'])}")
                raise ValueError(trans("financial_health_email_must_be_string", lang=lang))

            collection = get_mongo_collection()
            filter_criteria = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
            record = collection.find_one({**filter_criteria, 'step': 1})
            record_data = {
                'user_id': current_user.id if current_user.is_authenticated else None,
                'session_id': session['sid'],
                'step': 1,
                'first_name': form_data['first_name'],
                'email': form_data['email'],
                'user_type': form_data['user_type'],
                'send_email': form_data['send_email'],
                'created_at': datetime.utcnow()
            }
            document_id = None
            if record:
                record_data['_id'] = record['_id']
                collection.update_one(
                    {'_id': record['_id']},
                    {'$set': {k: v for k, v in record_data.items() if k != '_id'}}
                )
                document_id = record['_id']
            else:
                record_data['_id'] = str(uuid.uuid4())
                collection.insert_one(record_data)
                document_id = record_data['_id']

            current_app.logger.info(f"Step1 data updated/saved to MongoDB with ID {document_id} for session {session['sid']}")
            log_tool_usage(
                mongo,
                tool_name='financial_health',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='step1_submit'
            )

            session['health_step1'] = form_data
            session.modified = True
            return redirect(url_for('financial_health.step2'))
        
        return render_template('HEALTHSCORE/health_score_step1.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step1: {str(e)}")
        flash(f"{trans('financial_health_error_personal_info', lang=lang)} - {str(e)}", "danger")
        return render_template('HEALTHSCORE/health_score_step1.html', form=form, trans=trans, lang=lang), 500

@financial_health_bp.route('/step2', methods=['GET', 'POST'])
@custom_login_required
def step2():
    """Handle financial health step 2 form (income and expenses)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')
    if 'health_step1' not in session:
        flash(trans('financial_health_missing_step1', lang=lang, default='Please complete step 1 first.'), 'danger')
        return redirect(url_for('financial_health.step1'))
    form = Step2Form()
    current_app.logger.info(f"Starting step2 for session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
    log_tool_usage(
        mongo,
        tool_name='financial_health',
        user_id=current_user.id if current_user.is_authenticated else None,
        session_id=session['sid'],
        action='step2_view'
    )
    try:
        if request.method == 'POST':
            if not form.validate_on_submit():
                current_app.logger.error(f"Form validation failed: {form.errors}")
                flash(trans("financial_health_form_errors", lang=lang), "danger")
                return render_template('HEALTHSCORE/health_score_step2.html', form=form, trans=trans, lang=lang)

            collection = get_mongo_collection()
            filter_criteria = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
            record = collection.find_one({**filter_criteria, 'step': 2})
            record_data = {
                'user_id': current_user.id if current_user.is_authenticated else None,
                'session_id': session['sid'],
                'step': 2,
                'income': float(form.income.data),
                'expenses': float(form.expenses.data),
                'created_at': datetime.utcnow()
            }
            document_id = None
            if record:
                record_data['_id'] = record['_id']
                collection.update_one(
                    {'_id': record['_id']},
                    {'$set': {k: v for k, v in record_data.items() if k != '_id'}}
                )
                document_id = record['_id']
            else:
                record_data['_id'] = str(uuid.uuid4())
                collection.insert_one(record_data)
                document_id = record_data['_id']

            current_app.logger.info(f"Step2 data updated/saved to MongoDB with ID {document_id} for session {session['sid']}")
            log_tool_usage(
                mongo,
                tool_name='financial_health',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='step2_submit'
            )

            session['health_step2'] = {
                'income': float(form.income.data),
                'expenses': float(form.expenses.data),
            }
            session.modified = True
            return redirect(url_for('financial_health.step3'))
        
        return render_template('HEALTHSCORE/health_score_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step2: {str(e)}")
        flash(trans("financial_health_error_income_expenses", lang=lang), "danger")
        return render_template('HEALTHSCORE/health_score_step2.html', form=form, trans=trans, lang=lang), 500

@financial_health_bp.route('/step3', methods=['GET', 'POST'])
@custom_login_required
def step3():
    """Handle financial health step 3 form (debt and interest) and calculate score."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')
    if 'health_step2' not in session:
        flash(trans('financial_health_missing_step2', lang=lang, default='Please complete step 2 first.'), 'danger')
        return redirect(url_for('financial_health.step2'))
    form = Step3Form()
    current_app.logger.info(f"Starting step3 for session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
    log_tool_usage(
        mongo,
        tool_name='financial_health',
        user_id=current_user.id if current_user.is_authenticated else None,
        session_id=session['sid'],
        action='step3_view'
    )
    try:
        if request.method == 'POST':
            if not form.validate_on_submit():
                current_app.logger.error(f"Form validation failed: {form.errors}")
                flash(trans("financial_health_form_errors", lang=lang), "danger")
                return render_template('HEALTHSCORE/health_score_step3.html', form=form, trans=trans, lang=lang)

            step1_data = session.get('health_step1', {})
            step2_data = session.get('health_step2', {})
            debt = float(form.debt.data) if form.debt.data else 0
            interest_rate = float(form.interest_rate.data) if form.interest_rate.data else 0
            income = step2_data.get('income', 0)
            expenses = step2_data.get('expenses', 0)

            if income <= 0:
                current_app.logger.error("Income is zero or negative, cannot calculate financial health metrics")
                flash(trans("financial_health_income_zero_error", lang=lang), "danger")
                return render_template('HEALTHSCORE/health_score_step3.html', form=form, trans=trans, lang=lang), 500

            debt_to_income = (debt / income * 100) if income > 0 else 0
            savings_rate = ((income - expenses) / income * 100) if income > 0 else 0
            interest_burden = ((interest_rate * debt / 100) / 12) / income * 100 if debt > 0 and income > 0 else 0

            score = 100
            if debt_to_income > 0:
                score -= min(debt_to_income / 50, 50)
            if savings_rate < 0:
                score -= min(abs(savings_rate), 30)
            elif savings_rate > 0:
                score += min(savings_rate / 2, 20)
            score -= min(interest_burden, 20)
            score = max(0, min(100, round(score)))

            if score >= 80:
                status_key = "excellent"
                status = trans("financial_health_status_excellent", lang=lang)
            elif score >= 60:
                status_key = "good"
                status = trans("financial_health_status_good", lang=lang)
            else:
                status_key = "needs_improvement"
                status = trans("financial_health_status_needs_improvement", lang=lang)

            badges = []
            if score >= 80:
                badges.append(trans("financial_health_badge_financial_star", lang=lang))
            if debt_to_income < 20:
                badges.append(trans("financial_health_badge_debt_manager", lang=lang))
            if savings_rate >= 20:
                badges.append(trans("financial_health_badge_savings_pro", lang=lang))
            if interest_burden == 0 and debt > 0:
                badges.append(trans("financial_health_badge_interest_free", lang=lang))

            collection = get_mongo_collection()
            filter_criteria = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
            record = collection.find_one({**filter_criteria, 'step': 3})
            record_data = {
                'user_id': current_user.id if current_user.is_authenticated else None,
                'session_id': session['sid'],
                'step': 3,
                'first_name': step1_data.get('first_name', ''),
                'email': step1_data.get('email', ''),
                'user_type': step1_data.get('user_type', 'individual'),
                'income': income,
                'expenses': expenses,
                'debt': debt,
                'interest_rate': interest_rate,
                'debt_to_income': debt_to_income,
                'savings_rate': savings_rate,
                'interest_burden': interest_burden,
                'score': score,
                'status': status,
                'status_key': status_key,
                'badges': badges,
                'send_email': step1_data.get('send_email', False),
                'created_at': datetime.utcnow()
            }
            document_id = None
            if record:
                record_data['_id'] = record['_id']
                collection.update_one(
                    {'_id': record['_id']},
                    {'$set': {k: v for k, v in record_data.items() if k != '_id'}}
                )
                document_id = record['_id']
            else:
                record_data['_id'] = str(uuid.uuid4())
                collection.insert_one(record_data)
                document_id = record_data['_id']

            current_app.logger.info(f"Step3 data updated/saved to MongoDB with ID {document_id} for session {session['sid']}")
            log_tool_usage(
                mongo,
                tool_name='financial_health',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='step3_submit'
            )

            if step1_data.get('send_email', False) and step1_data.get('email'):
                try:
                    config = EMAIL_CONFIG["financial_health"]
                    subject = trans(config["subject_key"], lang=lang)
                    template = config["template"]
                    send_email(
                        app=current_app,
                        logger=current_app.logger,
                        to_email=step1_data['email'],
                        subject=subject,
                        template_name=template,
                        data={
                            "first_name": step1_data['first_name'],
                            "score": score,
                            "status": status,
                            "income": income,
                            "expenses": expenses,
                            "debt": debt,
                            "interest_rate": interest_rate,
                            "debt_to_income": debt_to_income,
                            "savings_rate": savings_rate,
                            "interest_burden": interest_burden,
                            "badges": badges,
                            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            "cta_url": url_for('financial_health.dashboard', _external=True)
                        },
                        lang=lang
                    )
                except Exception as e:
                    current_app.logger.error(f"Failed to send email: {str(e)}")
                    flash(trans("financial_health_email_failed", lang=lang), "warning")

            session.pop('health_step1', None)
            session.pop('health_step2', None)
            session.modified = True
            flash(trans("financial_health_health_completed_success", lang=lang), "success")
            return redirect(url_for('financial_health.dashboard'))
        
        return render_template('HEALTHSCORE/health_score_step3.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step3: {str(e)}")
        flash(trans("financial_health_unexpected_error", lang=lang), "danger")
        return render_template('HEALTHSCORE/health_score_step3.html', form=form, trans=trans, lang=lang), 500

@financial_health_bp.route('/dashboard', methods=['GET', 'POST'])
@custom_login_required
def dashboard():
    """Display financial health dashboard with comparison to others."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')
    current_app.logger.info(f"Starting dashboard for session {session['sid']} {'(anonymous)' if session.get('is_anonymous') else ''}")
    log_tool_usage(
        mongo,
        tool_name='financial_health',
        user_id=current_user.id if current_user.is_authenticated else None,
        session_id=session['sid'],
        action='dashboard_view'
    )
    try:
        collection = get_mongo_collection()
        filter_criteria = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
        stored_records = list(collection.find({**filter_criteria, 'step': 3}).sort('created_at', -1))
        if not stored_records:
            latest_record = {}
            records = []
        else:
            latest_record = stored_records[0]
            records = [(record['_id'], record) for record in stored_records]

        all_records = list(collection.find({'step': 3}))
        all_scores_for_comparison = [record['score'] for record in all_records if record.get('score') is not None]

        total_users = len(all_scores_for_comparison)
        rank = 0
        average_score = 0
        if all_scores_for_comparison:
            all_scores_for_comparison.sort(reverse=True)
            user_score = latest_record.get("score", 0)
            rank = sum(1 for s in all_scores_for_comparison if s > user_score) + 1
            average_score = sum(all_scores_for_comparison) / total_users

        insights = []
        tips = [
            trans("financial_health_tip_track_expenses", lang=lang),
            trans("financial_health_tip_ajo_savings", lang=lang),
            trans("financial_health_tip_pay_debts", lang=lang),
            trans("financial_health_tip_plan_expenses", lang=lang)
        ]
        if latest_record:
            if latest_record.get('debt_to_income', 0) > 40:
                insights.append(trans("financial_health_insight_high_debt", lang=lang))
            if latest_record.get('savings_rate', 0) < 0:
                insights.append(trans("financial_health_insight_negative_savings", lang=lang))
            elif latest_record.get('savings_rate', 0) >= 20:
                insights.append(trans("financial_health_insight_good_savings", lang=lang))
            if latest_record.get('interest_burden', 0) > 10:
                insights.append(trans("financial_health_insight_high_interest", lang=lang))
            if total_users >= 5:
                if rank <= total_users * 0.1:
                    insights.append(trans("financial_health_insight_top_10", lang=lang))
                elif rank <= total_users * 0.3:
                    insights.append(trans("financial_health_insight_top_30", lang=lang))
                else:
                    insights.append(trans("financial_health_insight_below_30", lang=lang))
            else:
                insights.append(trans("financial_health_insight_not_enough_users", lang=lang))
        else:
            insights.append(trans("financial_health_insight_no_data", lang=lang))

        return render_template(
            'HEALTHSCORE/health_score_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            rank=rank,
            total_users=total_users,
            average_score=average_score,
            trans=trans,
            lang=lang
        )
    except Exception as e:
        current_app.logger.exception(f"Critical error in dashboard: {str(e)}")
        flash(trans("financial_health_dashboard_load_error", lang=lang), "danger")
        return render_template(
            'HEALTHSCORE/health_score_dashboard.html',
            records=[],
            latest_record={},
            insights=[trans("financial_health_insight_no_data", lang=lang)],
            tips=[
                trans("financial_health_tip_track_expenses", lang=lang),
                trans("financial_health_tip_ajo_savings", lang=lang),
                trans("financial_health_tip_pay_debts", lang=lang),
                trans("financial_health_tip_plan_expenses", lang=lang)
            ],
            rank=0,
            total_users=0,
            average_score=0,
            trans=trans,
            lang=lang
        ), 500
