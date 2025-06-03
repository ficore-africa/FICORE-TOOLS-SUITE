from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, Email, NumberRange
from json_store import JsonStorage
from mailersend_email import send_email, EMAIL_CONFIG
from datetime import datetime
import uuid
import os

try:
    from app import trans
except ImportError:
    def trans(key, lang=None, **kwargs):
        return key.format(**kwargs)

emergency_fund_bp = Blueprint('emergency_fund', __name__, url_prefix='/emergency_fund')

def init_emergency_fund_storage(app):
    with app.app_context():
        app.logger.info("Initializing emergency fund storage")
        return JsonStorage('/tmp/data/emergency_fund.json' if os.environ.get('RENDER') else 'data/emergency_fund.json', logger_instance=app.logger)

def init_budget_storage(app):
    with app.app_context():
        app.logger.info("Initializing budget storage")
        return JsonStorage('/tmp/data/budget.json' if os.environ.get('RENDER') else 'data/budget.json', logger_instance=app.logger)

class CommaSeparatedFloatField(FloatField):
    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = float(valuelist[0].replace(',', ''))
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a valid number'))

class CommaSeparatedIntegerField(IntegerField):
    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = int(valuelist[0].replace(',', ''))
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a number'))

class Step1Form(FlaskForm):
    first_name = StringField(validators=[DataRequired()])
    email = StringField(validators=[Optional(), Email()])
    email_opt_in = BooleanField(default=False)
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.first_name.label.text = trans('emergency_fund_first_name', lang=lang)
        self.first_name.validators[0].message = trans('required_first_name', lang=lang, default='Please enter your first name.')
        self.email.label.text = trans('emergency_fund_email', lang=lang)
        self.email.validators[1].message = trans('emergency_fund_email_invalid', lang=lang, default='Please enter a valid email address.')
        self.email_opt_in.label.text = trans('emergency_fund_send_email', lang=lang)
        self.submit.label.text = trans('core_next', lang=lang)

class Step2Form(FlaskForm):
    monthly_expenses = CommaSeparatedFloatField(validators=[DataRequired(), NumberRange(min=0, max=10000000000)])
    monthly_income = CommaSeparatedFloatField(validators=[Optional(), NumberRange(min=0, max=10000000000)])
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.monthly_expenses.label.text = trans('emergency_fund_monthly_expenses', lang=lang)
        self.monthly_expenses.validators[0].message = trans('required_monthly_expenses', lang=lang, default='Please enter your monthly expenses.')
        self.monthly_expenses.validators[1].message = trans('emergency_fund_monthly_exceed', lang=lang, default='Amount exceeds maximum limit.')
        self.monthly_income.label.text = trans('emergency_fund_monthly_income', lang=lang)
        self.monthly_income.validators[1].message = trans('emergency_fund_monthly_exceed', lang=lang, default='Amount exceeds maximum limit.')
        self.submit.label.text = trans('core_next', lang=lang)

class Step3Form(FlaskForm):
    current_savings = CommaSeparatedFloatField(validators=[Optional(), NumberRange(min=0, max=10000000000)])
    risk_tolerance_level = SelectField(validators=[DataRequired()], choices=[
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High')
    ])
    dependents = CommaSeparatedIntegerField(validators=[Optional(), NumberRange(min=0, max=100)])
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.current_savings.label.text = trans('emergency_fund_current_savings', lang=lang)
        self.current_savings.validators[1].message = trans('emergency_fund_savings_max', lang=lang, default='Amount exceeds maximum limit.')
        self.risk_tolerance_level.label.text = trans('emergency_fund_risk_tolerance_level', lang=lang)
        self.risk_tolerance_level.validators[0].message = trans('required_risk_tolerance', lang=lang, default='Please select your risk tolerance.')
        self.risk_tolerance_level.choices = [
            ('low', trans('emergency_fund_risk_tolerance_level_low', lang=lang)),
            ('medium', trans('emergency_fund_risk_tolerance_level_medium', lang=lang)),
            ('high', trans('emergency_fund_risk_tolerance_level_high', lang=lang))
        ]
        self.dependents.label.text = trans('emergency_fund_dependents', lang=lang)
        self.dependents.validators[1].message = trans('emergency_fund_dependents_max', lang=lang, default='Number of dependents exceeds maximum.')
        self.submit.label.text = trans('core_next', lang=lang)

class Step4Form(FlaskForm):
    timeline = SelectField(validators=[DataRequired()], choices=[
        ('6', '6 Months'), ('12', '12 Months'), ('18', '18 Months')
    ])
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.timeline.label.text = trans('emergency_fund_timeline', lang=lang)
        self.timeline.validators[0].message = trans('required_timeline', lang=lang, default='Please select a timeline.')
        self.timeline.choices = [
            ('6', trans('emergency_fund_6_months', lang=lang)),
            ('12', trans('emergency_fund_12_months', lang=lang)),
            ('18', trans('emergency_fund_18_months', lang=lang))
        ]
        self.submit.label.text = trans('emergency_fund_calculate_button', lang=lang)

@emergency_fund_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    form = Step1Form()
    try:
        if request.method == 'POST':
            current_app.logger.info(f"Step1 POST data: {request.form.to_dict()}")
            if form.validate_on_submit():
                session['emergency_fund_step1'] = {
                    'first_name': form.first_name.data,
                    'email': form.email.data,
                    'email_opt_in': form.email_opt_in.data
                }
                session.modified = True
                current_app.logger.info(f"Step1 data saved to session: {session['emergency_fund_step1']}")
                return redirect(url_for('emergency_fund.step2'))
            else:
                current_app.logger.warning(f"Step1 form errors: {form.errors}")
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"{field}: {error}", 'danger')
        return render_template('emergency_fund_step1.html', form=form, step=1, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step1: {str(e)}")
        flash(trans('an_unexpected_error_occurred', lang=lang, default='An unexpected error occurred.'), 'danger')
        return render_template('emergency_fund_step1.html', form=form, step=1, trans=trans, lang=lang)

@emergency_fund_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    if 'sid' not in session or 'emergency_fund_step1' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        flash(trans('emergency_fund_missing_step1', lang=session.get('lang', 'en'), default='Please complete step 1 first.'), 'danger')
        return redirect(url_for('emergency_fund.step1'))
    lang = session.get('lang', 'en')
    form = Step2Form()
    try:
        if request.method == 'POST':
            current_app.logger.info(f"Step2 POST data: {request.form.to_dict()}")
            if form.validate_on_submit():
                session['emergency_fund_step2'] = {
                    'monthly_expenses': float(form.monthly_expenses.data),
                    'monthly_income': float(form.monthly_income.data) if form.monthly_income.data else None
                }
                session.modified = True
                current_app.logger.info(f"Step2 data saved to session: {session['emergency_fund_step2']}")
                return redirect(url_for('emergency_fund.step3'))
            else:
                current_app.logger.warning(f"Step2 form errors: {form.errors}")
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"{field}: {error}", 'danger')
        return render_template('emergency_fund_step2.html', form=form, step=2, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step2: {str(e)}")
        flash(trans('an_unexpected_error_occurred', lang=lang, default='An unexpected error occurred.'), 'danger')
        return render_template('emergency_fund_step2.html', form=form, step=2, trans=trans, lang=lang)

@emergency_fund_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    if 'sid' not in session or 'emergency_fund_step2' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        flash(trans('emergency_fund_missing_step2', lang=session.get('lang', 'en'), default='Please complete previous steps first.'), 'danger')
        return redirect(url_for('emergency_fund.step1'))
    lang = session.get('lang', 'en')
    form = Step3Form()
    try:
        if request.method == 'POST':
            current_app.logger.info(f"Step3 POST data: {request.form.to_dict()}")
            if form.validate_on_submit():
                session['emergency_fund_step3'] = {
                    'current_savings': float(form.current_savings.data) if form.current_savings.data else 0,
                    'risk_tolerance_level': form.risk_tolerance_level.data,
                    'dependents': int(form.dependents.data) if form.dependents.data else 0
                }
                session.modified = True
                current_app.logger.info(f"Step3 data saved to session: {session['emergency_fund_step3']}")
                return redirect(url_for('emergency_fund.step4'))
            else:
                current_app.logger.warning(f"Step3 form errors: {form.errors}")
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"{field}: {error}", 'danger')
        return render_template('emergency_fund_step3.html', form=form, step=3, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step3: {str(e)}")
        flash(trans('an_unexpected_error_occurred', lang=lang, default='An unexpected error occurred.'), 'danger')
        return render_template('emergency_fund_step3.html', form=form, step=3, trans=trans, lang=lang)

@emergency_fund_bp.route('/step4', methods=['GET', 'POST'])
def step4():
    if 'sid' not in session or 'emergency_fund_step3' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        flash(trans('emergency_fund_missing_step3', lang=session.get('lang', 'en'), default='Please complete previous steps first.'), 'danger')
        return redirect(url_for('emergency_fund.step1'))
    lang = session.get('lang', 'en')
    form = Step4Form()
    try:
        if request.method == 'POST':
            current_app.logger.info(f"Step4 POST data: {request.form.to_dict()}")
            if form.validate_on_submit():
                step1_data = session['emergency_fund_step1']
                step2_data = session['emergency_fund_step2']
                step3_data = session['emergency_fund_step3']
                months = int(form.timeline.data)
                base_target = step2_data['monthly_expenses'] * months
                recommended_months = months
                if step3_data['risk_tolerance_level'] == 'high':
                    recommended_months = max(12, months)
                elif step3_data['risk_tolerance_level'] == 'low':
                    recommended_months = min(6, months)
                if step3_data['dependents'] >= 2:
                    recommended_months += 2
                target_amount = step2_data['monthly_expenses'] * recommended_months
                gap = target_amount - step3_data['current_savings']
                monthly_savings = gap / months if gap > 0 else 0
                percent_of_income = None
                if step2_data['monthly_income'] and step2_data['monthly_income'] > 0:
                    percent_of_income = (monthly_savings / step2_data['monthly_income']) * 100
                badges = []
                if form.timeline.data in ['6', '12']:
                    badges.append('Planner')
                if step3_data['dependents'] >= 2:
                    badges.append('Protector')
                if gap <= 0:
                    badges.append('Steady Saver')
                if step3_data['current_savings'] >= target_amount:
                    badges.append('Fund Master')
                record = {
                    'id': str(uuid.uuid4()),
                    'session_id': session['sid'],
                    'data': {
                        'first_name': step1_data.get('first_name'),
                        'email': step1_data.get('email'),
                        'email_opt_in': step1_data.get('email_opt_in'),
                        'lang': lang,
                        'monthly_expenses': step2_data.get('monthly_expenses'),
                        'monthly_income': step2_data.get('monthly_income'),
                        'current_savings': step3_data.get('current_savings', 0),
                        'risk_tolerance_level': step3_data.get('risk_tolerance_level'),
                        'dependents': step3_data.get('dependents', 0),
                        'timeline': months,
                        'recommended_months': recommended_months,
                        'target_amount': target_amount,
                        'savings_gap': gap,
                        'monthly_savings': monthly_savings,
                        'percent_of_income': percent_of_income,
                        'badges': badges,
                        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                }
                emergency_fund_storage = current_app.config['STORAGE_MANAGERS']['emergency_fund']
                # Cache record in session before writing
                session['emergency_fund_cache'] = session.get('emergency_fund_cache', []) + [record]
                session.modified = True
                current_app.logger.info(f"Cached record {record['id']} in session for {session['sid']}")
                record_id = emergency_fund_storage.append(record, user_email=step1_data.get('email'), session_id=session['sid'], lang=lang)
                session['emergency_fund_record_id'] = record_id
                session.modified = True
                if step1_data['email_opt_in'] and step1_data['email']:
                    try:
                        config = EMAIL_CONFIG["emergency_fund"]
                        subject = trans(config["subject_key"], lang=lang)
                        template = config["template"]
                        send_email(
                            app=current_app,
                            logger=current_app.logger,
                            to_email=step1_data['email'],
                            subject=subject,
                            template_name=template,
                            data={
                                'first_name': step1_data['first_name'],
                                'lang': lang,
                                'monthly_expenses': step2_data['monthly_expenses'],
                                'monthly_income': step2_data['monthly_income'],
                                'current_savings': step3_data.get('current_savings', 0),
                                'risk_tolerance_level': step3_data['risk_tolerance_level'],
                                'dependents': step3_data.get('dependents', 0),
                                'timeline': months,
                                'recommended_months': recommended_months,
                                'target_amount': target_amount,
                                'savings_gap': gap,
                                'monthly_savings': monthly_savings,
                                'percent_of_income': percent_of_income,
                                'badges': badges,
                                'created_at': record['data']['created_at'],
                                'cta_url': url_for('emergency_fund.dashboard', _external=True),
                                'unsubscribe_url': url_for('emergency_fund.unsubscribe', email=step1_data['email'], _external=True)
                            },
                            lang=lang
                        )
                    except Exception as e:
                        current_app.logger.error(f"Failed to send email: {str(e)}")
                        flash(trans("email_send_failed", lang=lang), "danger")
                session['emergency_fund_step4'] = {'timeline': months}
                session.modified = True
                flash(trans('emergency_fund_completed_successfully', lang=lang, default='Emergency fund calculation completed successfully!'), 'success')
                for key in ['emergency_fund_step2', 'emergency_fund_step3']:
                    session.pop(key, None)
                session.modified = True
                return redirect(url_for('emergency_fund.dashboard'))
            else:
                current_app.logger.warning(f"Step4 form errors: {form.errors}")
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"{field}: {error}", 'danger')
        return render_template('emergency_fund_step4.html', form=form, step=4, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step4: {str(e)}")
        flash(trans('an_unexpected_error_occurred', lang=lang, default='An unexpected error occurred.'), 'danger')
        return render_template('emergency_fund_step4.html', form=form, step=4, trans=trans, lang=lang)

@emergency_fund_bp.route('/dashboard', methods=['GET'])
def dashboard():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    try:
        emergency_fund_storage = current_app.config['STORAGE_MANAGERS']['emergency_fund']
        budget_storage = current_app.config['STORAGE_MANAGERS']['budget']
        # Check session cache first
        user_data = []
        if 'emergency_fund_cache' in session:
            user_data = [r for r in session.get('emergency_fund_cache', []) if r.get('session_id') == session['sid']]
            current_app.logger.info(f"Retrieved {len(user_data)} records from session cache for session {session['sid']}")
        # Then check storage
        if not user_data:
            user_data = emergency_fund_storage.filter_by_session(session['sid'])
            current_app.logger.info(f"Retrieved {len(user_data)} records from storage for session {session['sid']}")
        email = None
        # Fallback to email
        if not user_data and 'emergency_fund_step1' in session and session['emergency_fund_step1'].get('email'):
            email = session['emergency_fund_step1']['email']
            user_data = [r for r in emergency_fund_storage.read_all() if r.get('user_email') == email]
            current_app.logger.info(f"Retrieved {len(user_data)} records for email {email}")
        # Fallback to record ID
        if not user_data and 'emergency_fund_record_id' in session:
            record = emergency_fund_storage.get_by_id(session['emergency_fund_record_id'])
            if record:
                user_data = [record]
                current_app.logger.info(f"Retrieved record {session['emergency_fund_record_id']} by ID")
        # Reconstruct from session data
        if not user_data and 'emergency_fund_step1' in session and 'emergency_fund_step4' in session:
            step1_data = session['emergency_fund_step1']
            step4_data = session['emergency_fund_step4']
            months = step4_data['timeline']
            latest_record = {
                'first_name': step1_data.get('first_name'),
                'email': step1_data.get('email'),
                'email_opt_in': step1_data.get('email_opt_in'),
                'lang': lang,
                'timeline': months,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            user_data = [{'id': session['sid'], 'data': latest_record}]
            current_app.logger.info(f"Reconstructed record from session for {session['sid']}")
        records = [(record['id'], record['data']) for record in user_data]
        latest_record = records[-1][1] if records else {}
        insights = []
        if latest_record:
            if latest_record.get('savings_gap', 0) <= 0:
                insights.append(trans('emergency_fund_insight_fully_funded', lang=lang))
            else:
                insights.append(trans('emergency_fund_insight_savings_gap', lang=lang,
                                    savings_gap=latest_record.get('savings_gap', 0),
                                    months=latest_record.get('timeline', 0)))
                if latest_record.get('percent_of_income') and latest_record.get('percent_of_income') > 30:
                    insights.append(trans('emergency_fund_insight_high_income_percentage', lang=lang))
                if latest_record.get('dependents', 0) > 2:
                    insights.append(trans('emergency_fund_insight_large_family', lang=lang,
                                        recommended_months=latest_record.get('recommended_months', 0)))
        cross_tool_insights = []
        budget_data = budget_storage.filter_by_session(session['sid']) or (budget_storage.filter_by_email(email) if email else [])
        if budget_data and latest_record and latest_record.get('savings_gap', 0) > 0:
            latest_budget = budget_data[-1]['data']
            if latest_budget.get('income') and latest_budget.get('expenses'):
                savings_possible = latest_budget['income'] - latest_budget['expenses']
                if savings_possible > 0:
                    cross_tool_insights.append(trans('emergency_fund_cross_tool_savings_possible', lang=lang,
                                                   amount=savings_possible))
        for key in ['emergency_fund_step1', 'emergency_fund_step4']:
            session.pop(key, None)
        session.modified = True
        return render_template(
            'emergency_fund_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            cross_tool_insights=cross_tool_insights,
            tips=[
                trans('emergency_fund_tip_automate_savings', lang=lang),
                trans('budget_tip_ajo_savings', lang=lang),
                trans('emergency_fund_tip_track_expenses', lang=lang),
                trans('budget_tip_monthly_savings', lang=lang)
            ],
            trans=trans,
            lang=lang
        )
    except Exception as e:
        current_app.logger.exception(f"Error in dashboard: {str(e)}")
        flash(trans('emergency_fund_load_dashboard_error', lang=lang), 'danger')
        return render_template(
            'emergency_fund_dashboard.html',
            records=[],
            latest_record={},
            insights=[],
            cross_tool_insights=[],
            tips=[
                trans('emergency_fund_tip_automate_savings', lang=lang),
                trans('budget_tip_ajo_savings', lang=lang),
                trans('emergency_fund_tip_track_expenses', lang=lang),
                trans('budget_tip_monthly_savings', lang=lang)
            ],
            trans=trans,
            lang=lang
        )

@emergency_fund_bp.route('/unsubscribe/<email>')
def unsubscribe(email):
    try:
        storage = current_app.config['STORAGE_MANAGERS']['emergency_fund']
        user_data = storage.get_all()
        updated = False
        for record in user_data:
            if record.get('user_email') == email and record['data'].get('email_opt_in', False):
                record['data']['email_opt_in'] = False
                storage.update_by_id(record['id'], record['data'])
                updated = True
        lang = session.get('lang', 'en')
        if updated:
            flash(trans("emergency_fund_unsubscribed_success", lang=lang), "success")
        else:
            flash(trans("emergency_fund_unsubscribe_failed", lang=lang), "danger")
            current_app.logger.error(f"Failed to unsubscribe email {email}")
        return redirect(url_for('index'))
    except Exception as e:
        current_app.logger.exception(f"Error in emergency_fund.unsubscribe: {str(e)}")
        flash(trans("emergency_fund_unsubscribe_error", lang=lang), "danger")
        return redirect(url_for('index'))

@emergency_fund_bp.route('/debug/storage', methods=['GET'])
def debug_storage():
    storage = current_app.config['STORAGE_MANAGERS']['emergency_fund']
    try:
        file_records = storage.read_all()
        session_records = session.get('emergency_fund_cache', []) if session else []
        file_exists = os.path.exists(storage.filename)
        backup_exists = os.path.exists(f"{storage.filename}.backup")
        file_size = os.path.getsize(storage.filename) if file_exists else 0
        backup_size = os.path.getsize(f"{storage.filename}.backup") if backup_exists else 0
        file_mtime = datetime.fromtimestamp(os.path.getmtime(storage.filename)).isoformat() if file_exists else None
        backup_mtime = datetime.fromtimestamp(os.path.getmtime(f"{storage.filename}.backup")).isoformat() if backup_exists else None
        session_config = {
            "permanent_session_lifetime": str(current_app.permanent_session_lifetime),
            "session_type": current_app.config.get('SESSION_TYPE', 'filesystem')
        }
        response = {
            "file_records": file_records,
            "session_records": session_records,
            "file_exists": file_exists,
            "backup_exists": backup_exists,
            "file_size_bytes": file_size,
            "backup_size_bytes": backup_size,
            "file_last_modified": file_mtime,
            "backup_last_modified": backup_mtime,
            "file_path": storage.filename,
            "backup_path": f"{storage.filename}.backup",
            "session_config": session_config
        }
        current_app.logger.info(f"Debug storage: {response}")
        return jsonify(response)
    except Exception as e:
        current_app.logger.error(f"Debug storage failed: {str(e)}")
        return jsonify({"error": str(e)}), 500
