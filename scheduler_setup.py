from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime, date, timedelta
from flask import current_app, url_for, session
from extensions import db
from models import Bill, User
from mailersend_email import send_email, trans, EMAIL_CONFIG
import atexit

def update_overdue_status():
    """Update status to overdue for past-due bills."""
    with current_app.app_context():
        try:
            today = date.today()
            bills = Bill.query.filter(Bill.status.in_(['pending', 'unpaid'])).all()
            for bill in bills:
                if bill.due_date < today:
                    bill.status = 'overdue'
            db.session.commit()
            current_app.logger.info(f"Updated {len(bills)} overdue bill statuses")
        except Exception as e:
            current_app.logger.exception(f"Error in update_overdue_status: {str(e)}")
            db.session.rollback()

def send_bill_reminders():
    """Send reminders for upcoming and overdue bills."""
    with current_app.app_context():
        try:
            today = date.today()
            user_bills = {}
            bills = Bill.query.all()
            for bill in bills:
                email = bill.user.email if bill.user_id and bill.user else bill.user_email
                lang = bill.user.lang if bill.user_id and bill.user else session.get('lang', 'en')
                if bill.send_email and email:
                    reminder_window = today + timedelta(days=bill.reminder_days or 7)
                    if (bill.status in ['pending', 'overdue'] or 
                        (today <= bill.due_date <= reminder_window)):
                        if email not in user_bills:
                            user_bills[email] = {
                                'first_name': bill.user.first_name if bill.user_id and bill.user else bill.first_name or 'User',
                                'bills': [],
                                'lang': lang
                            }
                        user_bills[email]['bills'].append({
                            'bill_name': bill.bill_name,
                            'amount': bill.amount,
                            'due_date': bill.due_date.strftime('%Y-%m-%d'),
                            'category': trans(f"bill_category_{bill.category}", lang=lang),
                            'status': trans(f"bill_status_{bill.status}", lang=lang)
                        })

            for email, data in user_bills.items():
                try:
                    config = EMAIL_CONFIG["bill_reminder"]
                    subject = trans(config["subject_key"], lang=data['lang'])
                    send_email(
                        app=current_app,
                        logger=current_app.logger,
                        to_email=email,
                        subject=subject,
                        template_name=config["template"],
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
    try:
        jobstores = {
            'default': SQLAlchemyJobStore(url=app.config['SQLALCHEMY_DATABASE_URI'])
        }
        scheduler = BackgroundScheduler(jobstores=jobstores)
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
        app.config['SCHEDULER'] = scheduler
        app.logger.info("Bill reminder and overdue status scheduler started successfully")
        atexit.register(lambda: scheduler.shutdown())
        return scheduler
    except Exception as e:
        app.logger.error(f"Failed to initialize scheduler: {str(e)}")
        raise
