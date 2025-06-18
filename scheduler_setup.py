from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from datetime import datetime, date, timedelta
from flask import current_app, url_for
from mailersend_email import send_email, trans, EMAIL_CONFIG
import time
import psutil
import os

def log_job_metrics(job_name):
    """Log duration and memory usage for a job."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            process = psutil.Process(os.getpid())
            start_memory = process.memory_info().rss / 1024 / 1024  # MB
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                end_memory = process.memory_info().rss / 1024 / 1024  # MB
                current_app.logger.info(
                    f"Job '{job_name}' completed: duration={duration:.2f}s, "
                    f"memory_start={start_memory:.2f}MB, memory_end={end_memory:.2f}MB"
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                end_memory = process.memory_info().rss / 1024 / 1024
                current_app.logger.error(
                    f"Job '{job_name}' failed: error={str(e)}, duration={duration:.2f}s, "
                    f"memory_start={start_memory:.2f}MB, memory_end={end_memory:.2f}MB",
                    exc_info=True
                )
                raise
        return wrapper
    return decorator

@log_job_metrics('update_overdue_status')
def update_overdue_status():
    """Update status to overdue for past-due bills."""
    with current_app.app_context():
        try:
            mongo = current_app.extensions['mongo']
            db = mongo.db
            bills_collection = db.bills
            today = date.today()
            bills = bills_collection.find({'status': {'$in': ['pending', 'unpaid']}})
            updated_count = 0
            for bill in bills:
                bill_due_date = bill['due_date']
                if isinstance(bill_due_date, str):
                    bill_due_date = datetime.strptime(bill_due_date, '%Y-%m-%d').date()
                if bill_due_date < today:
                    bills_collection.update_one(
                        {'_id': bill['_id']},
                        {'$set': {'status': 'overdue'}}
                    )
                    updated_count += 1
            current_app.logger.info(f"Updated {updated_count} overdue bill statuses")
        except Exception as e:
            current_app.logger.exception(f"Error in update_overdue_status: {str(e)}")
            raise

@log_job_metrics('send_bill_reminders')
def send_bill_reminders():
    """Send reminders for upcoming and overdue bills in batches."""
    with current_app.app_context():
        try:
            mongo = current_app.extensions['mongo']
            db = mongo.db
            bills_collection = db.bills
            bill_reminders_collection = db.bill_reminders
            users_collection = db.users
            today = date.today()
            user_bills = {}
            max_emails_per_run = 10  # Limit to 10 emails per job execution
            email_count = 0

            bills = bills_collection.find().limit(100)  # Process up to 100 bills per run
            for bill in bills:
                email = bill['user_email']
                user = users_collection.find_one({'email': email}, {'lang': 1})
                lang = user.get('lang', 'en') if user else 'en'
                if bill.get('send_email') and email:
                    reminder_window = today + timedelta(days=bill.get('reminder_days', 7))
                    bill_due_date = bill['due_date']
                    if isinstance(bill_due_date, str):
                        bill_due_date = datetime.strptime(bill_due_date, '%Y-%m-%d').date()
                    if (bill['status'] in ['pending', 'overdue'] or 
                        (today <= bill_due_date <= reminder_window)):
                        if email not in user_bills:
                            user_bills[email] = {
                                'first_name': bill.get('first_name', 'User'),
                                'bills': [],
                                'lang': lang
                            }
                        user_bills[email]['bills'].append({
                            'bill_name': bill['bill_name'],
                            'amount': bill['amount'],
                            'due_date': bill_due_date.strftime('%Y-%m-%d'),
                            'category': trans(f"bill_category_{bill['category']}", lang=lang),
                            'status': trans(f"bill_status_{bill['status']}", lang=lang)
                        })

            for email, data in user_bills.items():
                if email_count >= max_emails_per_run:
                    current_app.logger.info(f"Reached max emails ({max_emails_per_run}), stopping")
                    break
                try:
                    config = EMAIL_CONFIG["bill_reminder"]
                    subject = trans(config["subject_key"], lang=data['lang'])
                    reminder_data = {
                        'email': email,
                        'first_name': data['first_name'],
                        'bills': data['bills'],
                        'lang': data['lang'],
                        'sent_at': datetime.utcnow(),
                        'cta_url': url_for('bill.dashboard', _external=True),
                        'unsubscribe_url': url_for('bill.unsubscribe', email=email, _external=True)
                    }
                    send_email(
                        app=current_app,
                        logger=current_app.logger,
                        to_email=email,
                        subject=subject,
                        template_name=config["template"],
                        data=reminder_data,
                        lang=data['lang']
                    )
                    bill_reminders_collection.insert_one(reminder_data)
                    current_app.logger.info(f"Sent bill reminder email to {email} and saved to bill_reminders")
                    email_count += 1
                except Exception as e:
                    current_app.logger.error(f"Failed to send reminder email to {email}: {str(e)}")
            current_app.logger.info(f"Sent {email_count} bill reminder emails")
        except Exception as e:
            current_app.logger.error(f"Error in send_bill_reminders: {str(e)}", exc_info=True)
            raise

@log_job_metrics('cleanup_sessions')
def cleanup_sessions():
    """Remove expired sessions from the sessions collection."""
    with current_app.app_context():
        try:
            mongo = current_app.extensions['mongo']
            db = mongo.db
            sessions_collection = db.sessions
            result = sessions_collection.delete_many({
                'expiration': {'$lt': datetime.utcnow()}
            })
            current_app.logger.info(f"Deleted {result.deleted_count} expired sessions")
        except Exception as e:
            current_app.logger.error(f"Error in cleanup_sessions: {str(e)}", exc_info=True)
            raise

def init_scheduler(app, mongo):
    """Initialize the background scheduler."""
    with app.app_context():
        try:
            jobstores = {
                'default': MemoryJobStore()
            }
            scheduler = BackgroundScheduler(jobstores=jobstores)
            scheduler.add_job(
                func=update_overdue_status,
                trigger='interval',
                days=1,
                id='overdue_status',
                name='Update overdue bill statuses daily',
                replace_existing=True
            )
            scheduler.add_job(
                func=send_bill_reminders,
                trigger='interval',
                days=1,
                id='bill_reminders',
                name='Send bill reminders daily',
                replace_existing=True
            )
            scheduler.add_job(
                func=cleanup_sessions,
                trigger='interval',
                days=1,
                id='cleanup_sessions',
                name='Clean up expired sessions daily',
                replace_existing=True
            )
            scheduler.start()
            app.config['SCHEDULER'] = scheduler
            app.logger.info("Bill reminder, overdue status, and session cleanup scheduler started successfully")
            return scheduler
        except Exception as e:
            app.logger.error(f"Failed to initialize scheduler: {str(e)}", exc_info=True)
            raise RuntimeError(f"Scheduler initialization failed: {str(e)}")
