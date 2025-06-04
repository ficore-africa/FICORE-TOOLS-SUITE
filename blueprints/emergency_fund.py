from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, Email, NumberRange
from flask_login import current_user
from mailersend_email import send_email, EMAIL_CONFIG
from datetime import datetime
import uuid
import json
from translations import trans
from extensions import db
from models import EmergencyFund, Budget

emergency_fund_bp = Blueprint('emergency_fund', __name__, url_prefix='/emergency_fund')

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
    form_data = session.get('emergency_fund_step1', {})
    if current_user.is_authenticated:
        form_data['email'] = form_data.get('email', current_user.email)
        form_data['first_name'] = form_data.get('first_name', current_user.username)
    form = Step1Form(data=form_data)
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
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    if 'emergency_fund_step1' not in session:
        flash(trans('emergency_fund_missing_step1', lang=lang, default='Please complete step 1 first.'), 'danger')
        return redirect(url_for('emergency_fund.step1'))
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
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    if 'emergency_fund_step2' not in session:
        flash(trans('emergency_fund_missing_step2', lang=lang, default='Please complete previous steps first.'), 'danger')
        return redirect(url_for('emergency_fund.step1'))
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
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    if 'emergency_fund_step3' not in session:
        flash(trans('emergency_fund_missing_step3', lang=lang, default='Please complete previous steps first.'), 'danger')
        return redirect(url_for('emergency_fund.step1'))
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

                # Create and save EmergencyFund record to database
                emergency_fund = EmergencyFund(
                    id=str(uuid.uuid4()),
                    user_id=current_user.id if current_user.is_authenticated else None,
                    session_id=session['sid'],
                    first_name=step1_data.get('first_name'),
                    email=step1_data.get('email'),
                    email_opt_in=step1_data.get('email_opt_in'),
                    lang=lang,
                    monthly_expenses=step2_data.get('monthly_expenses'),
                    monthly_income=step2_data.get('monthly_income'),
                    current_savings=step3_data.get('current_savings', 0),
                    risk_tolerance_level=step3_data.get('risk_tolerance_level'),
                    dependents=step3_data.get('dependents', 0),
                    timeline=months,
                    recommended_months=recommended_months,
                    target_amount=target_amount,
                    savings_gap=gap,
                    monthly_savings=monthly_savings,
                    percent_of_income=percent_of_income,
                    badges=json.dumps(badges)
                )
                db.session.add(emergency_fund)
                db.session.commit()
                current_app.logger.info(f"Emergency fund record saved to database with ID {emergency_fund.id}")

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
                                'created_at': emergency_fund.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                                'cta_url': url_for('emergency_fund.dashboard', _external=True),
                                'unsubscribe_url': url_for('emergency_fund.unsubscribe', email=step1_data['email'], _external=True)
                            },
                            lang=lang
                        )
                    except Exception as e:
                        current_app.logger.error(f"Failed to send email: {str(e)}")
                        flash(trans("email_send_failed", lang=lang), "danger")

                # Clear session data after saving
                for key in ['emergency_fund_step1', 'emergency_fund_step2', 'emergency_fund_step3', 'emergency_fund_step4']:
                    session.pop(key, None)
                session.modified = True

                flash(trans('emergency_fund_completed_successfully', lang=lang, default='Emergency fund calculation completed successfully!'), 'success')
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
        # Filter by user_id if authenticated, else session_id
        filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
        user_data = EmergencyFund.query.filter_by(**filter_kwargs).order_by(EmergencyFund.created_at.desc()).all()
        current_app.logger.info(f"Retrieved {len(user_data)} records from database for session {session['sid']}")

        # If no records and authenticated, check by email
        if not user_data and current_user.is_authenticated and current_user.email:
            user_data = EmergencyFund.query.filter_by(email=current_user.email).order_by(EmergencyFund.created_at.desc()).all()
            current_app.logger.info(f"Retrieved {len(user_data)} records for email {current_user.email}")

        records = [(record.id, record.to_dict()) for record in user_data]
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
        budget_data = Budget.query.filter_by(**filter_kwargs).order_by(Budget.created_at.desc()).all()
        if budget_data and latest_record and latest_record.get('savings_gap', 0) > 0:
            latest_budget = budget_data[0]
            if latest_budget.income and latest_budget.fixed_expenses:
                savings_possible = latest_budget.income - latest_budget.fixed_expenses
                if savings_possible > 0:
                    cross_tool_insights.append(trans('emergency_fund_cross_tool_savings_possible', lang=lang,
                                                   amount=savings_possible))

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
        lang = session.get('lang', 'en')
        filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
        records = EmergencyFund.query.filter_by(email=email, **filter_kwargs).all()
        for record in records:
            record.email_opt_in = False
        db.session.commit()
        flash(trans("emergency_fund_unsubscribed_success", lang=lang), "success")
    except Exception as e:
        current_app.logger.exception(f"Error in emergency_fund.unsubscribe: {str(e)}")
        flash(trans("emergency_fund_unsubscribe_error", lang=lang), "danger")
    return redirect(url_for('index'))

@emergency_fund_bp.route('/debug/storage', methods=['GET'])
def debug_storage():
    try:
        filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
        records = EmergencyFund.query.filter_by(**filter_kwargs).all()
        record_dicts = [record.to_dict() for record in records]
        response = {
            "records": record_dicts,
            "count": len(records),
            "session_id": session['sid']
        }
        current_app.logger.info(f"Debug storage: {response}")
        return jsonify(response)
    except Exception as e:
        current_app.logger.error(f"Debug storage failed: {str(e)}")
        return jsonify({"error": str(e)}), 500
