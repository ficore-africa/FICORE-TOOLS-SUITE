from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, IntegerField, HiddenField
from wtforms.validators import DataRequired, NumberRange, Email, Optional
from json_store import JsonStorage
from mailersend_email import send_email, EMAIL_CONFIG
from datetime import datetime, date, timedelta
import uuid

try:
    from app import trans
except ImportError:
    def trans(key, lang=None):
        return key

bill_bp = Blueprint('bill', __name__, url_prefix='/bill')

def init_bill_storage(app):
    """Initialize bill_storage within app context."""
    with app.app_context():
        app.logger.info("Initializing bill storage")
        return JsonStorage('data/bills.json', logger_instance=app.logger)

def strip_commas(value):
    if isinstance(value, str):
        return value.replace(',', '')
    return value

# Form classes
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
    frequency = SelectField('Frequency')
    category = SelectField('Category')
    status = SelectField('Status')
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
        self.frequency.default = 'one-time'

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
        self.status.default = 'unpaid'

        self.send_email.label.text = trans('bill_send_email', lang)
        self.reminder_days.label.text = trans('bill_reminder_days', lang)

        self.process()

# Routes
@bill_bp.route('/form/step1', methods=['GET', 'POST'])
def form_step1():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')
    form = BillFormStep1()
    try:
        if request.method == 'POST' and form.validate_on_submit():
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
            return redirect(url_for('bill.form_step2'))
        return render_template('bill_form_step1.html', form=form, trans=trans, lang=lang)
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
    form = BillFormStep2()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            if form.send_email.data and not form.reminder_days.data:
                form.reminder_days.errors.append(trans('bill_reminder_days_required', lang))
                return render_template('bill_form_step2.html', form=form, trans=trans, lang=lang)
            bill_data = session.get('bill_step1', {})
            if not bill_data:
                flash(trans('bill_session_expired', lang), 'danger')
                current_app.logger.error("Session data missing for bill_step1")
                return redirect(url_for('bill.form_step1'))

            due_date = datetime.strptime(bill_data['due_date'], '%Y-%m-%d').date()
            status = form.status.data
            if status not in ['paid', 'pending'] and due_date < date.today():
                status = 'overdue'

            record = {
                'data': {
                    'first_name': bill_data['first_name'],
                    'bill_name': bill_data['bill_name'],
                    'amount': bill_data['amount'],
                    'due_date': bill_data['due_date'],
                    'frequency': form.frequency.data,
                    'category': form.category.data,
                    'status': status,
                    'send_email': form.send_email.data,
                    'reminder_days': form.reminder_days.data if form.send_email.data else None
                }
            }
            bill_storage = current_app.config['STORAGE_MANAGERS']['bills']
            bill_storage.append(record, user_email=bill_data['email'], session_id=session['sid'], lang=lang)

            if form.send_email.data and bill_data['email']:
                try:
                    config = EMAIL_CONFIG['bill_reminder']
                    subject = trans(config['subject_key'], lang=lang)
                    template = config['template']
                    send_email(
                        app=current_app,
                        logger=current_app.logger,
                        to_email=bill_data['email'],
                        subject=subject,
                        template_name=template,
                        data={
                            'first_name': bill_data['first_name'],
                            'bills': [{
                                'bill_name': bill_data['bill_name'],
                                'amount': bill_data['amount'],
                                'due_date': bill_data['due_date'],
                                'category': trans(f'bill_category_{form.category.data}', lang=lang),
                                'status': trans(f'bill_status_{status}', lang=lang)
                            }],
                            'cta_url': url_for('bill.dashboard', _external=True),
                            'unsubscribe_url': url_for('bill.unsubscribe', email=bill_data['email'], _external=True)
                        },
                        lang=lang
                    )
                except Exception as e:
                    current_app.logger.error(f"Failed to send email: {str(e)}")
                    flash(trans('email_send_failed', lang=lang), 'warning')

            flash(trans('bill_bill_added_dynamic_dashboard', lang=lang).format(
                bill_name=bill_data['bill_name'],
                dashboard_url=url_for('bill.dashboard')
            ), 'success')
            session.pop('bill_step1', None)
            if request.form.get('action') == 'save_and_continue':
                return redirect(url_for('bill.form_step1'))
            return redirect(url_for('bill.dashboard'))
        return render_template('bill_form_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in bill.form_step2: {str(e)}")
        flash(trans('bill_bill_form_load_error', lang), 'danger')
        return redirect(url_for('index'))

@bill_bp.route('/dashboard')
def dashboard():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
    lang = session.get('lang', 'en')
    try:
        bill_storage = current_app.config['STORAGE_MANAGERS']['bills']
        user_data = bill_storage.filter_by_session(session['sid'])
        bills = [(record['id'], record['data']) for record in user_data]
        paid_count = sum(1 for _, bill in bills if bill['status'] == 'paid')
        unpaid_count = sum(1 for _, bill in bills if bill['status'] == 'unpaid')
        overdue_count = sum(1 for _, bill in bills if bill['status'] == 'overdue')
        pending_count = sum(1 for _, bill in bills if bill['status'] == 'pending')
        total_paid = sum(bill['amount'] for _, bill in bills if bill['status'] == 'paid')
        total_unpaid = sum(bill['amount'] for _, bill in bills if bill['status'] == 'unpaid')
        total_overdue = sum(bill['amount'] for _, bill in bills if bill['status'] == 'overdue')
        total_bills = sum(bill['amount'] for _, bill in bills)

        categories = {}
        for _, bill in bills:
            cat = bill['category']
            categories[cat] = categories.get(cat, 0) + bill['amount']

        today = date.today()
        due_today = [(b_id, b) for b_id, b in bills if b['due_date'] == today.strftime('%Y-%m-%d')]
        due_week = [(b_id, b) for b_id, b in bills if today <= datetime.strptime(b['due_date'], '%Y-%m-%d').date() <= (today + timedelta(days=7))]
        due_month = [(b_id, b) for b_id, b in bills if today <= datetime.strptime(b['due_date'], '%Y-%m-%d').date() <= (today + timedelta(days=30))]
        upcoming_bills = [(b_id, b) for b_id, b in bills if today < datetime.strptime(b['due_date'], '%Y-%m-%d').date()]

        tips = [
            trans('bill_tip_pay_early', lang),
            trans('bill_tip_energy_efficient', lang),
            trans('bill_tip_plan_monthly', lang),
            trans('bill_tip_ajo_reminders', lang),
            trans('bill_tip_data_topup', lang)
        ]

        return render_template(
            'bill_dashboard.html',
            bills=bills,
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
        flash(trans('bill_dashboard_load_error', lang), 'danger')
        return render_template(
            'bill_dashboard.html',
            bills=[],
            paid_count=0,
            unpaid_count=0,
            overdue_count=0,
            pending_count=0,
            total_paid=0,
            total_unpaid=0,
            total_overdue=0,
            total_bills=0,
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
    bill_storage = current_app.config['STORAGE_MANAGERS']['bills']
    user_data = bill_storage.filter_by_session(session['sid'])
    bills = [(record['id'], record['data']) for record in user_data]

    try:
        if request.method == 'POST':
            action = request.form.get('action')
            bill_id = request.form.get('bill_id')

            if action == 'edit':
                record = bill_storage.get_by_id(bill_id)
                if record:
                    session['bill_data'] = record['data']
                    session['bill_id'] = bill_id
                    return redirect(url_for('bill.form_step1'))
                flash(trans('bill_bill_not_found', lang), 'danger')
                return redirect(url_for('bill.view_edit'))

            elif action == 'delete':
                try:
                    if bill_storage.delete_by_id(bill_id):
                        flash(trans('bill_bill_deleted_success', lang), 'success')
                    else:
                        flash(trans('bill_bill_delete_failed', lang), 'danger')
                        current_app.logger.error(f"Failed to delete bill ID {bill_id}")
                    return redirect(url_for('bill.dashboard'))
                except Exception as e:
                    current_app.logger.exception(f"Error in bill.view_edit (delete): {str(e)}")
                    flash(trans('bill_bill_delete_error', lang), 'danger')
                    return redirect(url_for('bill.dashboard'))

            elif action == 'toggle_status':
                try:
                    record = bill_storage.get_by_id(bill_id)
                    if record:
                        current_status = record['data']['status']
                        new_status = 'paid' if current_status == 'unpaid' else 'unpaid'
                        record['data']['status'] = new_status
                        if bill_storage.update_by_id(bill_id, record):
                            flash(trans('bill_bill_status_toggled_success', lang), 'success')
                            if new_status == 'paid' and record['data']['frequency'] != 'one-time':
                                try:
                                    old_due_date = datetime.strptime(record['data']['due_date'], '%Y-%m-%d').date()
                                    frequency = record['data']['frequency']
                                    if frequency == 'weekly':
                                        new_due_date = old_due_date + timedelta(days=7)
                                    elif frequency == 'monthly':
                                        new_due_date = old_due_date + timedelta(days=30)
                                    elif frequency == 'quarterly':
                                        new_due_date = old_due_date + timedelta(days=90)
                                    else:
                                        new_due_date = old_due_date  # Fallback for unexpected frequency
                                    new_record = {
                                        'data': {
                                            'first_name': record['data']['first_name'],
                                            'bill_name': record['data']['bill_name'],
                                            'amount': record['data']['amount'],
                                            'due_date': new_due_date.strftime('%Y-%m-%d'),
                                            'frequency': frequency,
                                            'category': record['data']['category'],
                                            'status': 'unpaid',
                                            'send_email': record['data']['send_email'],
                                            'reminder_days': record['data']['reminder_days']
                                        }
                                    }
                                    bill_storage.append(new_record, user_email=record.get('user_email'), session_id=session['sid'], lang=lang)
                                    flash(trans('bill_new_recurring_bill_success', lang).format(bill_name=record['data']['bill_name']), 'success')
                                except Exception as e:
                                    current_app.logger.exception(f"Error creating recurring bill: {str(e)}")
                                    flash(trans('bill_recurring_bill_error', lang), 'warning')
                        else:
                            flash(trans('bill_bill_status_toggle_failed', lang), 'danger')
                            current_app.logger.error(f"Failed to toggle status for bill ID {bill_id}")
                    else:
                        flash(trans('bill_bill_not_found', lang), 'danger')
                        current_app.logger.error(f"Bill ID {bill_id} not found")
                    return redirect(url_for('bill.dashboard'))
                except Exception as e:
                    current_app.logger.exception(f"Error in bill.view_edit (toggle_status): {str(e)}")
                    flash(trans('bill_error_toggling_status', lang), 'danger')
                    return redirect(url_for('bill.dashboard'))

        return render_template('view_edit_bills.html', bills=bills, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in bill.view_edit: {str(e)}")
        flash(trans('bill_view_edit_template_error', lang), 'danger')
        return redirect(url_for('bill.dashboard'))

@bill_bp.route('/unsubscribe/<email>')
def unsubscribe(email):
    try:
        lang = session.get('lang', 'en')
        bill_storage = current_app.config['STORAGE_MANAGERS']['bills']
        user_data = bill_storage.get_all()
        updated = False
        for record in user_data:
            if record.get('user_email') == email:
                record['data']['send_email'] = False
                if bill_storage.update_by_id(record['id'], record):
                    updated = True
        if updated:
            flash(trans('bill_unsubscribe_success', lang), 'success')
        else:
            flash(trans('bill_unsubscribe_failed', lang), 'danger')
            current_app.logger.error(f"Failed to unsubscribe email {email}")
        return redirect(url_for('index'))
    except Exception as e:
        current_app.logger.exception(f"Error in bill.unsubscribe: {str(e)}")
        flash(trans('bill_unsubscribe_error', lang), 'danger')
        return redirect(url_for('index'))
