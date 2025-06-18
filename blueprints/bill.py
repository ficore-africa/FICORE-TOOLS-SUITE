from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, IntegerField, HiddenField
from wtforms.validators import DataRequired, NumberRange, Email, Optional
from flask_login import current_user
from mailersend_email import send_email, EMAIL_CONFIG
from datetime import datetime, date, timedelta
import uuid
from translations import trans
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from extensions import mongo
from models import log_tool_usage
from session_utils import create_anonymous_session
from app import custom_login_required


bill_bp = Blueprint(
    'bill',
    __name__,
    template_folder='templates/BILL',
    url_prefix='/BILL'
)

bills_collection = mongo.db.bills

def strip_commas(value):
    """Remove commas from string values for numerical fields."""
    if isinstance(value, str):
        return value.replace(',', '')
    return value

def calculate_next_due_date(due_date, frequency):
    """Calculate the next due date based on frequency."""
    if frequency == 'weekly':
        return due_date + timedelta(days=7)
    elif frequency == 'monthly':
        return due_date + timedelta(days=30)
    elif frequency == 'quarterly':
        return due_date + timedelta(days=90)
    else:
        return due_date

class BillFormStep1(FlaskForm):
    first_name = StringField('First Name')
    email = StringField('Email')
    bill_name = StringField('Bill Name')
    amount = FloatField('Amount', filters=[strip_commas])
    due_date = StringField('Due Date (YYYY-MM-DD)')
    csrf_token = HiddenField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.first_name.validators = [DataRequired(message=trans('core_first_name_required', lang))]
        self.email.validators = [DataRequired(message=trans('core_email_required', lang)), Email()]
        self.bill_name.validators = [DataRequired(message=trans('bill_bill_name_required', lang))]
        self.amount.validators = [DataRequired(message=trans('bill_amount_required', lang)), NumberRange(min=0, max=10000000000)]
        self.due_date.validators = [DataRequired(message=trans('bill_due_date_required', lang))]

class BillFormStep2(FlaskForm):
    frequency = SelectField('Frequency', coerce=str)
    category = SelectField('Category', coerce=str)
    status = SelectField('Status', coerce=str)
    send_email = BooleanField('Send Email Reminders')
    reminder_days = IntegerField('Reminder Days', default=7)
    csrf_token = HiddenField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        self.frequency.validators = [DataRequired(message=trans('bill_frequency_required', lang))]
        self.category.validators = [DataRequired(message=trans('bill_category_required', lang))]
        self.status.validators = [DataRequired(message=trans('bill_status_required', lang))]
        self.reminder_days.validators = [Optional(), NumberRange(min=1, max=30, message=trans('bill_reminder_days_required', lang))]

        self.frequency.choices = [
            ('one-time', trans('bill_frequency_one_time', lang)),
            ('weekly', trans('bill_frequency_weekly', lang)),
            ('monthly', trans('bill_frequency_monthly', lang)),
            ('quarterly', trans('bill_frequency_quarterly', lang))
        ]
        self.category.choices = [
            ('utilities', trans('bill_category_utilities', lang)),
            ('rent', trans('bill_category_rent', lang)),
            ('data_internet', trans('bill_category_data_internet', lang)),
            ('ajo_esusu_adashe', trans('bill_category_ajo_esusu_adashe', lang)),
            ('food', trans('bill_category_food', lang)),
            ('transport', trans('bill_category_transport', lang)),
            ('clothing', trans('bill_category_clothing', lang)),
            ('education', trans('bill_category_education', lang)),
            ('healthcare', trans('bill_category_healthcare', lang)),
            ('entertainment', trans('bill_category_entertainment', lang)),
            ('airtime', trans('bill_category_airtime', lang)),
            ('school_fees', trans('bill_category_school_fees', lang)),
            ('savings_investments', trans('bill_category_savings_investments', lang)),
            ('other', trans('bill_category_other', lang))
        ]
        self.status.choices = [
            ('unpaid', trans('bill_status_unpaid', lang)),
            ('paid', trans('bill_status_paid', lang)),
            ('pending', trans('bill_status_pending', lang)),
            ('overdue', trans('bill_status_overdue', lang))
        ]
        self.send_email.label.text = trans('bill_send_email', lang)
        self.reminder_days.label.text = trans('bill_reminder_days', lang)

        self.frequency.default = self.frequency.choices[0][0]
        self.category.default = self.category.choices[0][0]
        self.status.default = self.status.choices[0][0]
        self.process()

        current_app.logger.info(f"BillFormStep2 initialized - frequency choices: {self.frequency.choices}, category choices: {self.category.choices}, status choices: {self.status.choices}")

@bill_bp.route('/form/step1', methods=['GET', 'POST'])
def form_step1():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')
    bill_data = session.get('bill_step1', {})
    if current_user.is_authenticated:
        bill_data['email'] = bill_data.get('email', current_user.email)
        bill_data['first_name'] = bill_data.get('first_name', current_user.username)
    form = BillFormStep1(data=bill_data)
    current_app.logger.info(f"BillFormStep1 initialized with data: {bill_data}")
    
    try:
        if request.method == 'POST' and form.validate_on_submit():
            log_tool_usage(
                mongo,
                tool_name='bill',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='form_step1_submit'
            )
            try:
                due_date = datetime.strptime(form.due_date.data, '%Y-%m-%d').date()
                if due_date < date.today():
                    flash(trans('bill_due_date_future_validation', lang), 'danger')
                    current_app.logger.error("Due date in the past in bill.form_step1")
                    return redirect(url_for('bill.form_step1'))
            except ValueError:
                flash(trans('bill_due_date_format_invalid', lang), 'danger')
                current_app.logger.error("Invalid due date format in bill.form_step1")
                return redirect(url_for('bill.form_step1'))

            session['bill_step1'] = {
                'first_name': form.first_name.data,
                'email': form.email.data,
                'bill_name': form.bill_name.data,
                'amount': form.amount.data,
                'due_date': form.due_date.data
            }
            current_app.logger.info(f"Step 1 session data saved: {session['bill_step1']}")
            return redirect(url_for('bill.form_step2'))
        log_tool_usage(
            mongo,
            tool_name='bill',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='form_step1_view'
        )
        return render_template('BILL/bill_form_step1.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in bill.form_step1: {str(e)}")
        flash(trans('bill_bill_form_load_error', lang), 'danger')
        return redirect(url_for('index'))

@bill_bp.route('/form/step2', methods=['GET', 'POST'])
def form_step2():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')
    bill_step2_data = session.get('bill_step2', {})
    bill_step1_data = session.get('bill_step1', {})
    form = BillFormStep2(data=bill_step2_data)
    current_app.logger.info(f"BillFormStep2 initialized with data: {bill_step2_data}")

    try:
        if request.method == 'POST':
            log_tool_usage(
                mongo,
                tool_name='bill',
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                action='form_step2_submit'
            )
            form_data = request.form.to_dict()
            current_app.logger.info(f"Form data received: {form_data}")
            current_app.logger.info(f"Submitted form values - frequency: {form.frequency.data or 'None'}, category: {form.category.data or 'None'}, status: {form.status.data or 'None'}, send_email: {form.send_email.data}, reminder_days: {form.reminder_days.data or 'None'}")

            if not form.csrf_token.validate(form):
                current_app.logger.error(f"CSRF validation failed: {form.csrf_token.errors}")
                flash(trans('bill_csrf_invalid', lang) or 'Invalid CSRF token', 'danger')
                return render_template('BILL/bill_form_step2.html', form=form, trans=trans, lang=lang)

            if form.validate_on_submit():
                current_app.logger.info("Form validated successfully")
                if form.send_email.data and not form.reminder_days.data:
                    form.reminder_days.errors.append(trans('bill_reminder_days_required', lang))
                    current_app.logger.error("Validation failed: reminder_days required when send_email is checked")
                    return render_template('BILL/bill_form_step2.html', form=form, trans=trans, lang=lang)

                if not bill_step1_data:
                    current_app.logger.error("Session data missing for bill_step1")
                    flash(trans('bill_session_expired', lang) or 'Session expired, please start over', 'danger')
                    return redirect(url_for('bill.form_step1'))

                try:
                    due_date = datetime.strptime(bill_step1_data['due_date'], '%Y-%m-%d').date()
                except ValueError:
                    current_app.logger.error("Invalid due date format in session data")
                    flash(trans('bill_due_date_format_invalid', lang) or 'Invalid due date format', 'danger')
                    return redirect(url_for('bill.form_step1'))

                required_fields = ['first_name', 'email', 'bill_name', 'amount', 'due_date']
                missing_fields = [field for field in required_fields if field not in bill_step1_data or bill_step1_data[field] is None]
                if missing_fields:
                    current_app.logger.error(f"Missing required fields in bill_step1: {missing_fields}")
                    flash(trans('bill_missing_fields', lang) or f"Missing required fields: {', '.join(missing_fields)}", 'danger')
                    return redirect(url_for('bill.form_step1'))

                status = form.status.data
                if status not in ['paid', 'pending'] and due_date < date.today():
                    status = 'overdue'

                bill_id = session.get('bill_id')
                filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
                bill_data = {
                    'user_id': current_user.id if current_user.is_authenticated else None,
                    'session_id': session['sid'],
                    'user_email': bill_step1_data['email'],
                    'first_name': bill_step1_data['first_name'],
                    'bill_name': bill_step1_data['bill_name'],
                    'amount': float(bill_step1_data['amount']),
                    'due_date': due_date.isoformat(),  # Convert datetime.date to ISO string
                    'frequency': form.frequency.data,
                    'category': form.category.data,
                    'status': status,
                    'send_email': form.send_email.data,
                    'reminder_days': form.reminder_days.data if form.send_email.data else None
                }

                if bill_id:
                    # Update existing bill
                    bill = bills_collection.find_one({'_id': ObjectId(bill_id), **filter_kwargs})
                    if bill:
                        bills_collection.update_one(
                            {'_id': ObjectId(bill_id), **filter_kwargs},
                            {'$set': bill_data}
                        )
                        current_app.logger.info(f"Bill updated successfully: {bill_id}, category={bill_data['category']}, frequency={bill_data['frequency']}")
                        flash(trans('bill_updated_success', lang) or 'Bill updated successfully', 'success')
                    else:
                        flash(trans('bill_not_found', lang) or 'Bill not found', 'danger')
                        return redirect(url_for('bill.dashboard'))
                else:
                    # Create new bill
                    bill_data['_id'] = ObjectId()
                    bills_collection.insert_one(bill_data)
                    current_app.logger.info(f"Bill saved successfully for {bill_step1_data['email']}: {bill_data['bill_name']}, category={bill_data['category']}, frequency={bill_data['frequency']}")
                    flash(trans('bill_added_success', lang) or 'Bill added successfully', 'success')

                if form.send_email.data and bill_step1_data['email']:
                    try:
                        config = EMAIL_CONFIG['bill_reminder']
                        subject = trans(config['subject_key'], lang=lang)
                        template = config['template']
                        send_email(
                            app=current_app,
                            logger=current_app.logger,
                            to_email=bill_step1_data['email'],
                            subject=subject,
                            template_name=template,
                            data={
                                'first_name': bill_step1_data['first_name'],
                                'bills': [{
                                    'bill_name': bill_step1_data['bill_name'],
                                    'amount': bill_step1_data['amount'],
                                    'due_date': bill_step1_data['due_date'],  # Use session string format for email
                                    'category': trans(f'bill_category_{form.category.data}', lang=lang),
                                    'status': trans(f'bill_status_{status}', lang=lang)
                                }],
                                'cta_url': url_for('bill.dashboard', _external=True),
                                'unsubscribe_url': url_for('bill.unsubscribe', email=bill_step1_data['email'], _external=True)
                            },
                            lang=lang
                        )
                        current_app.logger.info(f"Email sent to {bill_step1_data['email']}")
                    except Exception as e:
                        current_app.logger.error(f"Failed to send email: {str(e)}")
                        flash(trans('email_send_failed', lang) or 'Failed to send email reminder', 'warning')

                session.pop('bill_step1', None)
                session.pop('bill_id', None)
                session.pop('bill_step2', None)

                action = form_data.get('action')
                if action == 'save_and_continue':
                    current_app.logger.info("Redirecting to bill.form_step1")
                    return redirect(url_for('bill.form_step1'))
                current_app.logger.info("Redirecting to bill.dashboard")
                return redirect(url_for('bill.dashboard'))
            else:
                current_app.logger.error(f"Form validation failed: {form.errors}")
                for field, errors in form.errors.items():
                    for err_msg in errors:
                        flash(f"{trans(f'bill_{field}', lang=lang)}: {err_msg}", 'danger')
                return render_template('BILL/bill_form_step2.html', form=form, trans=trans, lang=lang)
        log_tool_usage(
            mongo,
            tool_name='bill',
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session['sid'],
            action='form_step2_view'
        )
        return render_template('BILL/bill_form_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in bill.form_step2: {str(e)}")
        flash(trans('bill_bill_form_load_error', lang) or 'Error loading bill form', 'danger')
        return redirect(url_for('index'))

@bill_bp.route('/dashboard')
def dashboard():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')

    log_tool_usage(
        mongo,
        tool_name='bill',
        user_id=current_user.id if current_user.is_authenticated else None,
        session_id=session['sid'],
        action='dashboard_view'
    )

    tips = [
        trans('bill_tip_pay_early', lang),
        trans('bill_tip_energy_efficient', lang),
        trans('bill_tip_plan_monthly', lang),
        trans('bill_tip_ajo_reminders', lang),
        trans('bill_tip_data_topup', lang)
    ]

    try:
        filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}
        bills = bills_collection.find(filter_kwargs)
        bills_data = [(str(bill['_id']), bill) for bill in bills]

        paid_count = 0
        unpaid_count = 0
        overdue_count = 0
        pending_count = 0
        total_paid = 0.0
        total_unpaid = 0.0
        total_overdue = 0.0
        total_bills = 0.0
        categories = {}
        due_today = []
        due_week = []
        due_month = []
        upcoming_bills = []

        today = date.today()
        for b_id, bill in bills_data:
            try:
                bill_amount = float(bill['amount'])
            except (ValueError, TypeError):
                current_app.logger.warning(f"Skipping invalid bill record {b_id}: invalid amount {bill.get('amount')}")
                continue

            total_bills += bill_amount
            cat = bill['category']
            categories[cat] = categories.get(cat, 0) + bill_amount

            if bill['status'] == 'paid':
                paid_count += 1
                total_paid += bill_amount
            elif bill['status'] == 'unpaid':
                unpaid_count += 1
                total_unpaid += bill_amount
            elif bill['status'] == 'overdue':
                overdue_count += 1
                total_overdue += bill_amount
            elif bill['status'] == 'pending':
                pending_count += 1

            try:
                bill_due_date = datetime.strptime(bill['due_date'], '%Y-%m-%d').date()  # Parse string to datetime.date
                if bill_due_date == today:
                    due_today.append((b_id, bill))
                if today <= bill_due_date <= (today + timedelta(days=7)):
                    due_week.append((b_id, bill))
                if today <= bill_due_date <= (today + timedelta(days=30)):
                    due_month.append((b_id, bill))
                if today < bill_due_date:
                    upcoming_bills.append((b_id, bill))
            except ValueError:
                current_app.logger.warning(f"Skipping invalid bill record {b_id}: invalid due_date {bill.get('due_date')}")
                continue

        return render_template(
            'BILL/bill_dashboard.html',
            bills=bills_data,
            paid_count=paid_count,
            unpaid_count=unpaid_count,
            overdue_count=overdue_count,
            pending_count=pending_count,
            total_paid=total_paid,
            total_unpaid=total_unpaid,
            total_overdue=total_overdue,
            total_bills=total_bills,
            categories=categories,
            due_today=due_today,
            due_week=due_week,
            due_month=due_month,
            upcoming_bills=upcoming_bills,
            tips=tips,
            trans=trans,
            lang=lang
        )
    except Exception as e:
        current_app.logger.exception(f"Error in bill.dashboard: {str(e)}")
        flash(trans('bill_dashboard_load_error', lang) or 'Error loading bill dashboard', 'danger')
        return render_template(
            'BILL/bill_dashboard.html',
            bills=[],
            paid_count=0,
            unpaid_count=0,
            overdue_count=0,
            pending_count=0,
            total_paid=0.0,
            total_unpaid=0.0,
            total_overdue=0.0,
            total_bills=0.0,
            categories={},
            due_today=[],
            due_week=[],
            due_month=[],
            upcoming_bills=[],
            tips=tips,
            trans=trans,
            lang=lang
        )

@bill_bp.route('/view_edit', methods=['GET', 'POST'])
def view_edit():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')
    filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}

    log_tool_usage(
        mongo,
        tool_name='bill',
        user_id=current_user.id if current_user.is_authenticated else None,
        session_id=session['sid'],
        action='view_edit_view'
    )

    try:
        bills = bills_collection.find(filter_kwargs)
        bills_data = []
        for bill in bills:
            try:
                due_date = bill['due_date']
                if isinstance(due_date, str):
                    due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
            except ValueError:
                current_app.logger.warning(f"Invalid due_date format for bill {bill['_id']}: {due_date}")
                due_date = None
            form = BillFormStep2(
                data={
                    'frequency': bill['frequency'],
                    'category': bill['category'],
                    'status': bill['status'],
                    'send_email': bill['send_email'],
                    'reminder_days': bill['reminder_days'],
                    'csrf_token': None
                }
            )
            bills_data.append((str(bill['_id']), bill, form))

        if request.method == 'POST':
            action = request.form.get('action')
            bill_id = request.form.get('bill_id')
            bill = bills_collection.find_one({'_id': ObjectId(bill_id), **filter_kwargs})
            if not bill:
                flash(trans('bill_bill_not_found', lang) or 'Bill not found', 'danger')
                return redirect(url_for('bill.view_edit'))

            if action == 'update':
                log_tool_usage(
                    mongo,
                    tool_name='bill',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    session_id=session['sid'],
                    action='update_bill'
                )
                form = BillFormStep2()
                if form.validate_on_submit():
                    try:
                        bills_collection.update_one(
                            {'_id': ObjectId(bill_id), **filter_kwargs},
                            {'$set': {
                                'frequency': form.frequency.data,
                                'category': form.category.data,
                                'status': form.status.data,
                                'send_email': form.send_email.data,
                                'reminder_days': form.reminder_days.data if form.send_email.data else None
                            }}
                        )
                        current_app.logger.info(f"Bill updated successfully: {bill_id}, category={form.category.data}, frequency={form.frequency.data}")
                        flash(trans('bill_updated_success', lang) or 'Bill updated successfully', 'success')
                    except Exception as e:
                        current_app.logger.error(f"Failed to update bill ID {bill_id}: {str(e)}")
                        flash(trans('bill_update_failed', lang) or 'Failed to update bill', 'danger')
                else:
                    current_app.logger.error(f"Form validation failed: {form.errors}")
                    for field, errors in form.errors.items():
                        for err_msg in errors:
                            flash(f"{trans(f'bill_{field}', lang=lang)}: {err_msg}", 'danger')
                return redirect(url_for('bill.view_edit'))

            elif action == 'edit':
                log_tool_usage(
                    mongo,
                    tool_name='bill',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    session_id=session['sid'],
                    action='edit_bill'
                )
                try:
                    due_date = bill['due_date']
                    if isinstance(due_date, str):
                        due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
                except ValueError:
                    current_app.logger.error(f"Invalid due_date format for bill {bill_id}: {bill['due_date']}")
                    flash(trans('bill_due_date_format_invalid', lang) or 'Invalid due date format', 'danger')
                    return redirect(url_for('bill.view_edit'))
                session['bill_step1'] = {
                    'first_name': bill['first_name'],
                    'email': bill['user_email'],
                    'bill_name': bill['bill_name'],
                    'amount': bill['amount'],
                    'due_date': due_date.strftime('%Y-%m-%d')
                }
                session['bill_step2'] = {
                    'frequency': bill['frequency'],
                    'category': bill['category'],
                    'status': bill['status'],
                    'send_email': bill['send_email'],
                    'reminder_days': bill['reminder_days']
                }
                session['bill_id'] = str(bill['_id'])
                current_app.logger.info(f"Redirecting to edit bill: {bill_id}, category={bill['category']}, frequency={bill['frequency']}")
                return redirect(url_for('bill.form_step1'))

            elif action == 'delete':
                log_tool_usage(
                    mongo,
                    tool_name='bill',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    session_id=session['sid'],
                    action='delete_bill'
                )
                try:
                    bills_collection.delete_one({'_id': ObjectId(bill_id), **filter_kwargs})
                    current_app.logger.info(f"Bill deleted successfully: {bill_id}")
                    flash(trans('bill_bill_deleted_success', lang) or 'Bill deleted successfully', 'success')
                except Exception as e:
                    current_app.logger.error(f"Failed to delete bill ID {bill_id}: {str(e)}")
                    flash(trans('bill_bill_delete_failed', lang) or 'Failed to delete bill', 'danger')
                return redirect(url_for('bill.dashboard'))

            elif action == 'toggle_status':
                log_tool_usage(
                    mongo,
                    tool_name='bill',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    session_id=session['sid'],
                    action='toggle_status'
                )
                try:
                    current_status = bill['status']
                    new_status = 'paid' if current_status == 'unpaid' else 'unpaid'
                    bills_collection.update_one(
                        {'_id': ObjectId(bill_id), **filter_kwargs},
                        {'$set': {'status': new_status}}
                    )
                    current_app.logger.info(f"Bill status toggled: {bill_id}, new_status={new_status}")
                    flash(trans('bill_bill_status_toggled_success', lang) or 'Bill status updated', 'success')
                    if new_status == 'paid' and bill['frequency'] != 'one-time':
                        try:
                            due_date = bill['due_date']
                            if isinstance(due_date, str):
                                due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
                        except ValueError:
                            current_app.logger.error(f"Invalid due_date format for bill {bill_id}: {bill['due_date']}")
                            flash(trans('bill_due_date_format_invalid', lang) or 'Invalid due date format', 'danger')
                            return redirect(url_for('bill.view_edit'))
                        new_due_date = calculate_next_due_date(due_date, bill['frequency'])
                        new_bill = {
                            '_id': ObjectId(),
                            'user_id': bill['user_id'],
                            'session_id': bill['session_id'],
                            'user_email': bill['user_email'],
                            'first_name': bill['first_name'],
                            'bill_name': bill['bill_name'],
                            'amount': bill['amount'],
                            'due_date': new_due_date.isoformat(),  # Convert to ISO string
                            'frequency': bill['frequency'],
                            'category': bill['category'],
                            'status': 'unpaid',
                            'send_email': bill['send_email'],
                            'reminder_days': bill['reminder_days']
                        }
                        bills_collection.insert_one(new_bill)
                        current_app.logger.info(f"New recurring bill created: {new_bill['_id']}")
                        flash(trans('bill_new_recurring_bill_success', lang).format(bill_name=bill['bill_name']), 'success')
                except Exception as e:
                    current_app.logger.error(f"Failed to toggle status for bill ID {bill_id}: {str(e)}")
                    flash(trans('bill_bill_status_toggle_failed', lang) or 'Failed to update bill status', 'danger')
                return redirect(url_for('bill.dashboard'))

        return render_template('BILL/view_edit_bills.html', bills_data=bills_data, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in bill.view_edit: {str(e)}")
        flash(trans('bill_view_edit_template_error', lang) or 'Error loading bill edit page', 'danger')
        return redirect(url_for('bill.dashboard'))

@bill_bp.route('/unsubscribe/<email>')
def unsubscribe():
    log_tool_usage(
        mongo,
        tool_name='bill',
        user_id=current_user.id if current_user.is_authenticated else None,
        session_id=session['sid'],
        action='unsubscribe'
    )
    try:
        lang = session.get('lang', 'en')
        bills_collection.update_many(
            {'user_email': email},
            {'$set': {'send_email': False}}
        )
        current_app.logger.info(f"Unsubscribed email: {email}")
        flash(trans('bill_unsubscribe_success', lang) or 'Unsubscribed successfully', 'success')
    except Exception as e:
        current_app.logger.error(f"Error unsubscribing email {email}: {str(e)}")
        flash(trans('bill_unsubscribe_failed', lang) or 'Failed to unsubscribe', 'danger')
    return redirect(url_for('index'))
