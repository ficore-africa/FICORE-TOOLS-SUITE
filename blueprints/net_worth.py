from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email, ValidationError
from json_store import JsonStorage
from mailersend_email import send_email, EMAIL_CONFIG
from datetime import datetime
import uuid

try:
    from app import trans
except ImportError:
    def trans(key, lang=None):
        return key

net_worth_bp = Blueprint('net_worth', __name__, url_prefix='/net_worth')

def init_storage(app):
    """Initialize storage with app context."""
    with app.app_context():
        storage = JsonStorage('/tmp/data/networth.json', logger_instance=current_app.logger)
        current_app.logger.debug("Initialized JsonStorage for net_worth")
        return storage

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
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')
    form = Step1Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            form_data = form.data.copy()
            session['networth_step1_data'] = form_data
            session.modified = True
            current_app.logger.info(f"Net worth step1 form data saved for session {session['sid']}: {form_data}")
            return redirect(url_for('net_worth.step2'))
        return render_template('net_worth_step1.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error in net_worth.step1: {str(e)}", extra={'session_id': session.get('sid')})
        flash(trans("net_worth_error_personal_info", lang=lang), "danger")
        return render_template('net_worth_step1.html', form=form, trans=trans, lang=lang), 500

@net_worth_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle net worth step 2 form (assets)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')
    form = Step2Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
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
        return render_template('net_worth_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error in net_worth.step2: {str(e)}", extra={'session_id': session.get('sid')})
        flash(trans("net_worth_error_assets", lang=lang), "danger")
        return render_template('net_worth_step2.html', form=form, trans=trans, lang=lang), 500

@net_worth_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    """Calculate net worth."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')
    form = Step3Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            step1_data = session.get('networth_step1_data', {})
            step2_data = session.get('networth_step2_data', {})
            form_data = form.data.copy()

            # Store step3 data in session
            session['networth_step3_data'] = {'loans': form_data.get('loans', 0) or 0}
            session.modified = True
            current_app.logger.info(f"Net worth step3 form data saved for session {session['sid']}: {session['networth_step3_data']}")

            # Calculate assets and liabilities
            cash_savings = step2_data.get('cash_savings', 0)
            investments = step2_data.get('investments', 0)
            property = step2_data.get('property', 0)
            loans = form_data.get('loans', 0) or 0

            total_assets = cash_savings + investments + property
            total_liabilities = loans
            net_worth = total_assets - total_liabilities

            # Assign badges
            badges = []
            if net_worth > 0:
                badges.append('net_worth_badge_wealth_builder')
            if total_liabilities == 0:
                badges.append('net_worth_badge_debt_free')
            if cash_savings >= total_assets * 0.3:
                badges.append('net_worth_badge_savings_champion')
            if property >= total_assets * 0.5:
                badges.append('net_worth_badge_property_mogul')

            # Store record with session_id for easy retrieval
            record = {
                "id": str(uuid.uuid4()),
                "session_id": session['sid'],
                "data": {
                    "first_name": step1_data.get('first_name', ''),
                    "email": step1_data.get('email', ''),
                    "send_email": step1_data.get('send_email', False),
                    "cash_savings": cash_savings,
                    "investments": investments,
                    "property": property,
                    "loans": loans,
                    "total_assets": total_assets,
                    "total_liabilities": total_liabilities,
                    "net_worth": net_worth,
                    "badges": badges,
                    "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }

            # Save to storage with logging
            storage = current_app.config['STORAGE_MANAGERS']['net_worth']
            try:
                storage.append(record, user_email=step1_data.get('email'), session_id=session['sid'], lang=lang)
                session['networth_record_id'] = record['id']
                session.modified = True
                current_app.logger.info(f"Successfully saved record {record['id']} for session {session['sid']}")
            except Exception as storage_error:
                current_app.logger.error(f"Failed to save net worth record: {str(storage_error)}", extra={'session_id': session['sid']})
                flash(trans("net_worth_storage_error", lang=lang), "danger")
                return render_template('net_worth_step3.html', form=form, trans=trans, lang=lang), 500

            # Send email if requested
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
                            "first_name": record["data"]["first_name"],
                            "cash_savings": record["data"]["cash_savings"],
                            "investments": record["data"]["investments"],
                            "property": record["data"]["property"],
                            "loans": record["data"]["loans"],
                            "total_assets": record["data"]["total_assets"],
                            "total_liabilities": record["data"]["total_liabilities"],
                            "net_worth": record["data"]["net_worth"],
                            "badges": record["data"]["badges"],
                            "created_at": record["data"]["created_at"],
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
        return render_template('net_worth_step3.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.error(f"Error in net_worth.step3: {str(e)}", extra={'session_id': session.get('sid')})
        flash(trans("net_worth_calculation_error", lang=lang), "danger")
        return render_template('net_worth_step3.html', form=form, trans=trans, lang=lang), 500

@net_worth_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Display net worth dashboard."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')

    try:
        storage = current_app.config['STORAGE_MANAGERS']['net_worth']
        user_data = []
        latest_record = {}

        # Step 1: Try to get data from storage by session ID
        try:
            user_data = storage.filter_by_session(session['sid'])
            current_app.logger.info(f"Found {len(user_data)} records for session {session['sid']}")
        except Exception as e:
            current_app.logger.warning(f"filter_by_session failed: {str(e)}", extra={'session_id': session['sid']})
            user_data = []

        # Step 2: If no data, try to get by record ID
        if not user_data and 'networth_record_id' in session:
            try:
                all_records = storage.read_all()
                for record in all_records:
                    if record.get('id') == session['networth_record_id']:
                        user_data = [record]
                        break
                current_app.logger.info(f"Found {len(user_data)} records by record ID {session['networth_record_id']}")
            except Exception as e:
                current_app.logger.warning(f"Read by record ID failed: {str(e)}", extra={'session_id': session['sid']})
                user_data = []

        # Step 3: If still no data, construct from session data
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
                    "first_name": step1_data.get('first_name', ''),
                    "email": step1_data.get('email', ''),
                    "send_email": step1_data.get('send_email', False),
                    "cash_savings": cash_savings,
                    "investments": investments,
                    "property": property,
                    "loans": loans,
                    "total_assets": total_assets,
                    "total_liabilities": total_liabilities,
                    "net_worth": net_worth,
                    "badges": badges,
                    "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                user_data = [{"id": session['sid'], "data": latest_record}]
            else:
                current_app.logger.info(f"No session data available for construction for session {session['sid']}")

        # Process records
        if user_data and not latest_record:
            records = [(record["id"], record["data"]) for record in user_data]
            latest_record = records[-1][1] if records else {}
        elif latest_record:
            records = [(session['sid'], latest_record)]
        else:
            records = []

        # Additional logging for debugging
        current_app.logger.info(f"records: {records}")
        current_app.logger.info(f"latest_record: {latest_record}")

        # Generate insights and tips
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

        # Clear session data only after successful rendering
        if latest_record:
            session.pop('networth_step1_data', None)
            session.pop('networth_step2_data', None)
            session.pop('networth_step3_data', None)
            session.modified = True

        current_app.logger.info(f"Dashboard rendering with {len(records)} records for session {session['sid']}")
        return render_template(
            'net_worth_dashboard.html',
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
            'net_worth_dashboard.html',
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
def unsubscribe(email):
    """Unsubscribe user from net worth emails."""
    try:
        storage = current_app.config['STORAGE_MANAGERS']['net_worth']
        user_data = storage.get_all()
        updated = False
        for record in user_data:
            if record.get('user_email') == email and record['data'].get('send_email', False):
                record['data']['send_email'] = False
                if storage.update_by_id(record['id'], record):
                    updated = True
        lang = session.get('lang', 'en')
        if updated:
            flash(trans("net_worth_unsubscribed_success", lang=lang), "success")
        else:
            flash(trans("net_worth_unsubscribe_failed", lang=lang), "danger")
            current_app.logger.error(f"Failed to unsubscribe email {email}")
        return redirect(url_for('index'))
    except Exception as e:
        current_app.logger.exception(f"Error in net_worth.unsubscribe: {str(e)}")
        flash(trans("net_worth_unsubscribe_error", lang=lang), "danger")
        return redirect(url_for('index'))
