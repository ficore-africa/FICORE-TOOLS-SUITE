from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, date, timedelta
from flask import current_app, url_for
from mailersend_email import send_email, EMAIL_CONFIG
from json_store import JsonStorage

try:
    from app import trans
except ImportError:
    def trans(key, lang=None):
        return key

def update_overdue_status():
    """Update status to overdue for past-due bills."""
    with current_app.app_context():
        try:
            bill_storage = current_app.config['STORAGE_MANAGERS']['bills']
            user_data = bill_storage.get_all()
            today = date.today()
            for record in user_data:
                bill = record['data']
                due_date = datetime.strptime(bill['due_date'], '%Y-%m-%d').date()
                if due_date < today and bill['status'] not in ['paid', 'pending']:
                    bill['status'] = 'overdue'
                    bill_storage.update_by_id(record['id'], record)
            current_app.logger.info("Updated overdue statuses")
        except Exception as e:
            current_app.logger.exception(f"Error in update_overdue_status: {str(e)}")

def send_bill_reminders():
    """Send reminders for upcoming and overdue bills."""
    with current_app.app_context():
        try:
            bill_storage = current_app.config['STORAGE_MANAGERS']['bills']
            user_data = bill_storage.get_all()
            today = date.today()

            # Group bills by user email
            user_bills = {}
            for record in user_data:
                bill = record['data']
                email = record.get('user_email')
                lang = record.get('lang', 'en')
                due_date = datetime.strptime(bill['due_date'], '%Y-%m-%d').date()
                send_email = bill.get('send_email', False)
                reminder_days = bill.get('reminder_days', 7)
                reminder_window = today + timedelta(days=reminder_days)

                if send_email and email:
                    if (bill['status'] in ['pending', 'overdue'] or 
                        (today <= due_date <= reminder_window)):
                        if email not in user_bills:
                            user_bills[email] = {
                                'first_name': bill['first_name'],
                                'bills': [],
                                'lang': lang
                            }
                        user_bills[email]['bills'].append({
                            'bill_name': bill['bill_name'],
                            'amount': bill['amount'],
                            'due_date': bill['due_date'],
                            'category': trans(f"bill_category_{bill['category']}", lang=lang),
                            'status': trans(f"bill_status_{bill['status']}", lang=lang)
                        })

            # Send emails
            for email, data in user_bills.items():
                try:
                    config = EMAIL_CONFIG["bill_reminder"]
                    subject = trans(config["subject_key"], lang=data['lang'])
                    template = config["template"]
                    send_email(
                        app=current_app,
                        logger=current_app.logger,
                        to_email=email,
                        subject=subject,
                        template_name=template,
                        data={
                            'first_name': data['first_name'],
                            'bills': data['bills'],
                            'cta_url': url_for('bill.dashboard', _external=True),
                            'unsubscribe_url': url_for('bill.unsubscribe', email=email, _external=True)
                        },
                        lang=data['lang']
                    )
                    current_app.logger.info(f"Sent bill reminder email to {email}")
                except Exception as e:
                    current_app.logger.error(f"Failed to send reminder email to {email}: {str(e)}")

        except Exception as e:
            current_app.logger.exception(f"Error in send_bill_reminders: {str(e)}")

def init_scheduler(app):
    """Initialize the background scheduler."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=send_bill_reminders,
        trigger='interval',
        days=1,
        id='bill_reminders',
        name='Send bill reminders daily',
        replace_existing=True
    )
    scheduler.add_job(
        func=update_overdue_status,
        trigger='interval',
        days=1,
        id='overdue_status',
        name='Update overdue bill statuses daily',
        replace_existing=True
    )
    scheduler.start()
    app.logger.info("Bill reminder and overdue status scheduler started")
    return scheduler