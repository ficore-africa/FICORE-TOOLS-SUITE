from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email, ValidationError
from flask_login import current_user
from translations import trans
from mailersend_email import send_email, EMAIL_CONFIG
from datetime import datetime
import uuid
import json
from models import log_tool_usage  # Import log_tool_usage
from extensions import mongo
from session_utils import create_anonymous_session
from app import custom_login_required

net_worth_bp = Blueprint(
    'net_worth',
    __name__,
    template_folder='templates/NETWORTH',
    url_prefix='/NETWORTH'
)

class Step1Form(FlaskForm):
    first_name = StringField()
    email = StringField()
    send_email = BooleanField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.first_name.label.text = trans('net_worth_first_name', lang=lang)
        self.email.label.text = trans('net_worth_email', lang=lang)
        self.send_email.label.text = trans('net_worth_send_email', lang=lang)
        self.submit.label.text = trans('net_worth_next', lang=lang)
        self.first_name.validators = [DataRequired(message=trans('net_worth_first_name_required', lang=lang))]
        self.email.validators = [Optional(), Email(message=trans('net_worth_email_invalid', lang=lang))]

class Step2Form(FlaskForm):
    cash_savings = FloatField()
    investments = FloatField()
    property = FloatField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.cash_savings.label.text = trans('net_worth_cash_savings', lang=lang)
        self.investments.label.text = trans('net_worth_investments', lang=lang)
        self.property.label.text = trans('net_worth_property', lang=lang)
        self.submit.label.text = trans('net_worth_next', lang=lang)
        self.cash_savings.validators = [
            DataRequired(message=trans('net_worth_cash_savings_required', lang=lang)),
            NumberRange(min=0, max=10000000000, message=trans('net_worth_cash_savings_max', lang=lang))
        ]
        self.investments.validators = [
            DataRequired(message=trans('net_worth_investments_required', lang=lang)),
            NumberRange(min=0, max=10000000000, message=trans('net_worth_investments_max', lang=lang))
        ]
        self.property.validators = [
            DataRequired(message=trans('net_worth_property_required', lang=lang)),
            NumberRange(min=0, max=10000000000, message=trans('net_worth_property_max', lang=lang))
        ]

    def validate_cash_savings(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data)
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid cash_savings input: {field.data}", extra={'session_id': session.get('sid', 'unknown')})
                raise ValidationError(trans('net_worth_cash_savings_invalid', lang=session.get('lang', 'en')))

    def validate_investments(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data)
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid investments input: {field.data}", extra={'session_id': session.get('sid', 'unknown')})
                raise ValidationError(trans('net_worth_investments_invalid', lang=session.get('lang', 'en')))

    def validate_property(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data)
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid property input: {field.data}", extra={'session_id': session.get('sid', 'unknown')})
                raise ValidationError(trans('net_worth_property_invalid', lang=session.get('lang', 'en')))

class Step3Form(FlaskForm):
    loans = FloatField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.loans.label.text = trans('net_worth_loans', lang=lang)
        self.submit.label.text = trans('net_worth_submit', lang=lang)
        self.loans.validators = [
            Optional(),
            NumberRange(min=0, max=10000000000, message=trans('net_worth_loans_max', lang=lang))
        ]

    def validate_loans(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data) if cleaned_data else None
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid loans input: {field.data}", extra={'session_id': session.get('sid', 'unknown')})
                raise ValidationError(trans('net_worth_loans_invalid', lang=session.get('lang', 'en')))

@net_worth_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle net worth step 1 form (personal info)."""
    if 'sid' not in session:
        create_anonymous_session()
        logger.debug(f"New anonymous session created with sid: {session['sid']}", extra={'session_id': session['sid']})
    lang = session.get('lang', 'en')
    form_data = session.get('networth_step1_data', {})
    if current_user.is_authenticated:
        form_data['email'] = form_data.get('email', current_user.email)
        form_data['first_name'] = form_data.get('first_name', current_user.username)
    form = Step1Form(data=form_data)
    try:
        if request.method == 'POST':
            log_tool_usage(
                tool_name='net_worth',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='step1_submit',
                mongo=mongo
            )
            if form.validate_on_submit():
                form_data = form.data.copy()
                session['networth_step1_data'] = form_data
                session.modified = True
                current_app.logger.info(f"Net worth step1 form data saved for session {session['sid']}: {form_data}")
                return redirect(url_for('net_worth.step2'))
            else:
                current_app.logger.warning(f"Form validation failed: {form.errors}")
                flash(trans("net_worth_form_validation_error", lang=lang), "danger")
        log_tool_usage(
            tool_name='net_worth',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='step1_view',
            mongo=mongo
        )
        return render_template('NETWORTH/net_worth_step1.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error in net_worth.step1: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        flash(trans("net_worth_error_personal_info", lang=lang), "danger")
        return render_template('NETWORTH/net_worth_step1.html', form=form, trans=trans, lang=lang), 500

@net_worth_bp.route('/step2', methods=['GET', 'POST'])
@custom_login_required
def step2():
    """Handle net worth step 2 form (assets)."""
    if 'sid' not in session:
        create_anonymous_session()
        logger.debug(f"New anonymous session created with sid: {session['sid']}", extra={'session_id': session['sid']})
    lang = session.get('lang', 'en')
    if 'networth_step1_data' not in session:
        flash(trans('net_worth_missing_step1', lang=lang, default='Please complete step 1 first.'), 'danger')
        return redirect(url_for('net_worth.step1'))
    form = Step2Form()
    try:
        if request.method == 'POST':
            log_tool_usage(
                tool_name='net_worth',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='step2_submit',
                mongo=mongo
            )
            if form.validate_on_submit():
                form_data = {
                    'cash_savings': float(form.cash_savings.data),
                    'investments': float(form.investments.data),
                    'property': float(form.property.data),
                    'submit': form.submit.data
                }
                session['networth_step2_data'] = form_data
                session.modified = True
                current_app.logger.info(f"Net worth step2 form data saved for session {session['sid']}: {form_data}")
                return redirect(url_for('net_worth.step3'))
            else:
                current_app.logger.warning(f"Form validation failed: {form.errors}")
                flash(trans("net_worth_form_validation_error", lang=lang), "danger")
        log_tool_usage(
            tool_name='net_worth',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='step2_view',
            mongo=mongo
        )
        return render_template('NETWORTH/net_worth_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error in net_worth.step2: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        flash(trans("net_worth_error_assets", lang=lang), "danger")
        return render_template('NETWORTH/net_worth_step2.html', form=form, trans=trans, lang=lang), 500

@net_worth_bp.route('/step3', methods=['GET', 'POST'])
@custom_login_required
def step3():
    """Calculate net worth and persist to MongoDB."""
    if 'sid' not in session:
        create_anonymous_session()
        logger.debug(f"New anonymous session created with sid: {session['sid']}", extra={'session_id': session['sid']})
    lang = session.get('lang', 'en')
    if 'networth_step2_data' not in session:
        flash(trans('net_worth_missing_step2', lang=lang, default='Please complete step 2 first.'), 'danger')
        return redirect(url_for('net_worth.step1'))
    form = Step3Form()
    try:
        if request.method == 'POST':
            log_tool_usage(
                tool_name='net_worth',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='step3_submit',
                mongo=mongo
            )
            if form.validate_on_submit():
                step1_data = session.get('networth_step1_data', {})
                step2_data = session.get('networth_step2_data', {})
                form_data = form.data.copy()

                session['networth_step3_data'] = {'loans': form_data.get('loans', 0) or 0}
                session.modified = True
                current_app.logger.info(f"Net worth step3 form data saved for session {session['sid']}: {session['networth_step3_data']}")

                cash_savings = step2_data.get('cash_savings', 0)
                investments = step2_data.get('investments', 0)
                property = step2_data.get('property', 0)
                loans = form_data.get('loans', 0) or 0

                total_assets = cash_savings + investments + property
                total_liabilities = loans
                net_worth = total_assets - total_liabilities

                badges = []
                if net_worth > 0:
                    badges.append('net_worth_badge_wealth_builder')
                if total_liabilities == 0:
                    badges.append('net_worth_badge_debt_free')
                if cash_savings >= total_assets * 0.3:
                    badges.append('net_worth_badge_savings_champion')
                if property >= total_assets * 0.5:
                    badges.append('net_worth_badge_property_mogul')

                # Save to MongoDB
                net_worth_record = {
                    '_id': str(uuid.uuid4()),
                    'user_id': current_user.id if current_user.is_authenticated else None,
                    'session_id': session['sid'],
                    'first_name': step1_data.get('first_name', ''),
                    'email': step1_data.get('email', ''),
                    'send_email': step1_data.get('send_email', False),
                    'cash_savings': cash_savings,
                    'investments': investments,
                    'property': property,
                    'loans': loans,
                    'total_assets': total_assets,
                    'total_liabilities': total_liabilities,
                    'net_worth': net_worth,
                    'badges': badges,
                    'created_at': datetime.utcnow()
                }
                mongo.db.net_worth_data.insert_one(net_worth_record)
                session['networth_record_id'] = net_worth_record['_id']
                session.modified = True
                current_app.logger.info(f"Successfully saved record {net_worth_record['_id']} for session {session['sid']}")

                email = step1_data.get('email')
                send_email_flag = step1_data.get('send_email', False)
                if send_email_flag and email:
                    try:
                        config = EMAIL_CONFIG["net_worth"]
                        subject = trans(config["subject_key"], lang=lang)
                        template = config["template"]
                        send_email(
                            app=current_app,
                            logger=current_app.logger,
                            to_email=email,
                            subject=subject,
                            template_name=template,
                            data={
                                "first_name": net_worth_record['first_name'],
                                "cash_savings": net_worth_record['cash_savings'],
                                "investments": net_worth_record['investments'],
                                "property": net_worth_record['property'],
                                "loans": net_worth_record['loans'],
                                "total_assets": net_worth_record['total_assets'],
                                "total_liabilities": net_worth_record['total_liabilities'],
                                "net_worth": net_worth_record['net_worth'],
                                "badges": net_worth_record['badges'],
                                "created_at": net_worth_record['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                                "cta_url": url_for('net_worth.dashboard', _external=True),
                                "unsubscribe_url": url_for('net_worth.unsubscribe', email=email, _external=True)
                            },
                            lang=lang
                        )
                    except Exception as e:
                        current_app.logger.error(f"Failed to send email: {str(e)}")
                        flash(trans("net_worth_email_failed", lang=lang), "warning")

                flash(trans("net_worth_success", lang=lang), "success")
                return redirect(url_for('net_worth.dashboard'))
            else:
                current_app.logger.warning(f"Form validation failed: {form.errors}")
                flash(trans("net_worth_form_validation_error", lang=lang), "danger")
        log_tool_usage(
            tool_name='net_worth',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='step3_view',
            mongo=mongo
        )
        return render_template('NETWORTH/net_worth_step3.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error in net_worth.step3: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        flash(trans("net_worth_calculation_error", lang=lang), "danger")
        return render_template('NETWORTH/net_worth_step3.html', form=form, trans=trans, lang=lang), 500

@net_worth_bp.route('/dashboard', methods=['GET', 'POST'])
@custom_login_required
def dashboard():
    """Display net worth dashboard using MongoDB data."""
    if 'sid' not in session:
        create_anonymous_session()
        logger.debug(f"New anonymous session created with sid: {session['sid']}", extra={'session_id': session['sid']})
    lang = session.get('lang', 'en')
    try:
        log_tool_usage(
            tool_name='net_worth',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='dashboard_view',
            mongo=mongo
        )
        # Fetch records by user_id or session_id
        user_records = mongo.db.net_worth_data.find(
            {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
        ).sort('created_at', -1)
        user_data = [(record['_id'], record) for record in user_records]

        # Fallback to email for authenticated users
        if not user_data and current_user.is_authenticated and current_user.email:
            user_records = mongo.db.net_worth_data.find({'email': current_user.email}).sort('created_at', -1)
            user_data = [(record['_id'], record) for record in user_records]

        # Fallback to record ID
        if not user_data and 'networth_record_id' in session:
            record = mongo.db.net_worth_data.find_one({'_id': session['networth_record_id']})
            if record:
                user_data = [(record['_id'], record)]

        # Reconstruct from session data if no records found
        if not user_data:
            step1_data = session.get('networth_step1_data', {})
            step2_data = session.get('networth_step2_data', {})
            step3_data = session.get('networth_step3_data', {})

            if step1_data and step2_data:
                current_app.logger.info(f"Constructing record from session data for session {session['sid']}")
                cash_savings = step2_data.get('cash_savings', 0)
                investments = step2_data.get('investments', 0)
                property = step2_data.get('property', 0)
                loans = step3_data.get('loans', 0) or 0

                total_assets = cash_savings + investments + property
                total_liabilities = loans
                net_worth = total_assets - total_liabilities

                badges = []
                if net_worth > 0:
                    badges.append('net_worth_badge_wealth_builder')
                if total_liabilities == 0:
                    badges.append('net_worth_badge_debt_free')
                if cash_savings >= total_assets * 0.3:
                    badges.append('net_worth_badge_savings_champion')
                if property >= total_assets * 0.5:
                    badges.append('net_worth_badge_property_mogul')

                latest_record = {
                    '_id': session['sid'],
                    'user_id': current_user.id if current_user.is_authenticated else None,
                    'session_id': session['sid'],
                    'created_at': datetime.utcnow(),
                    'first_name': step1_data.get('first_name', ''),
                    'email': step1_data.get('email', ''),
                    'send_email': step1_data.get('send_email', False),
                    'cash_savings': cash_savings,
                    'investments': investments,
                    'property': property,
                    'loans': loans,
                    'total_assets': total_assets,
                    'total_liabilities': total_liabilities,
                    'net_worth': net_worth,
                    'badges': badges
                }
                user_data = [(session['sid'], latest_record)]
        else:
            latest_record = user_data[-1][1] if user_data else {}

        # Process records for display
        records = user_data
        insights = []
        tips = [
            trans("net_worth_tip_track_ajo", lang=lang),
            trans("net_worth_tip_review_property", lang=lang),
            trans("net_worth_tip_pay_loans_early", lang=lang),
            trans("net_worth_tip_diversify_investments", lang=lang)
        ]

        if latest_record:
            if latest_record.get('total_liabilities', 0) > latest_record.get('total_assets', 0) * 0.5:
                insights.append(trans("net_worth_insight_high_loans", lang=lang))
            if latest_record.get('cash_savings', 0) < latest_record.get('total_assets', 0) * 0.1:
                insights.append(trans("net_worth_insight_low_cash", lang=lang))
            if latest_record.get('investments', 0) >= latest_record.get('total_assets', 0) * 0.3:
                insights.append(trans("net_worth_insight_strong_investments", lang=lang))
            if latest_record.get('net_worth', 0) <= 0:
                insights.append(trans("net_worth_insight_negative_net_worth", lang=lang))

        if user_data:
            session.pop('networth_step1_data', None)
            session.pop('networth_step2_data', None)
            session.pop('networth_step3_data', None)
            session.modified = True

        current_app.logger.info(f"Dashboard rendering with {len(records)} records for session {session['sid']}")
        return render_template(
            'NETWORTH/net_worth_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            trans=trans,
            lang=lang
        )
    except Exception as e:
        current_app.logger.error(f"Error in net_worth.dashboard: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        flash(trans("net_worth_dashboard_load_error", lang=lang), "danger")
        return render_template(
            'NETWORTH/net_worth_dashboard.html',
            records=[],
            latest_record={},
            insights=[],
            tips=[
                trans("net_worth_tip_track_ajo", lang=lang),
                trans("net_worth_tip_review_property", lang=lang),
                trans("net_worth_tip_pay_loans_early", lang=lang),
                trans("net_worth_tip_diversify_investments", lang=lang)
            ],
            trans=trans,
            lang=lang
        ), 500

@net_worth_bp.route('/unsubscribe/<email>')
@custom_login_required
def unsubscribe(email):
    """Unsubscribe user from net worth emails using MongoDB."""
    if 'sid' not in session:
        create_anonymous_session()
        logger.debug(f"New anonymous session created with sid: {session['sid']}", extra={'session_id': session['sid']})
    lang = session.get('lang', 'en')
    try:
        log_tool_usage(
            tool_name='net_worth',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='unsubscribe',
            mongo=mongo
        )
        result = mongo.db.net_worth_data.update_many(
            {'email': email, 'user_id': current_user.id if current_user.is_authenticated else {'$exists': False}},
            {'$set': {'send_email': False}}
        )
        if result.modified_count > 0:
            flash(trans("net_worth_unsubscribed_success", lang=lang), "success")
        else:
            flash(trans("net_worth_unsubscribe_failed", lang=lang), "danger")
            current_app.logger.error(f"Failed to unsubscribe email {email}")
        return redirect(url_for('index'))
    except Exception as e:
        current_app.logger.exception(f"Error in net_worth.unsubscribe: {str(e)}")
        flash(trans("net_worth_unsubscribe_error", lang=lang), "danger")
        return redirect(url_for('index'))
