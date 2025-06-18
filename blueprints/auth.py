from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from translations import trans
from models import create_user, get_user, get_user_by_email, update_user, get_referrals, log_tool_usage
import logging
import uuid
from datetime import datetime, timedelta
import os
from extensions import mongo
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import smtplib
from email.mime.text import MIMEText
from session_utils import create_anonymous_session

# Configure logging
logger = logging.getLogger('ficore_app')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Define the auth blueprint
auth_bp = Blueprint('auth', __name__, template_folder='templates/auth', url_prefix='/auth')

# Forms
class SignupForm(FlaskForm):
    username = StringField(validators=[DataRequired(), Length(min=3, max=80)], render_kw={
        'placeholder': trans('auth_username_placeholder', default='e.g., chukwuma123'),
        'title': trans('auth_username_tooltip', default='Choose a unique username')
    })
    email = StringField(validators=[DataRequired(), Email()], render_kw={
        'placeholder': trans('core_email_placeholder', default='e.g., user@example.com'),
        'title': trans('core_email_tooltip', default='Enter your email address')
    })
    password = PasswordField(validators=[DataRequired(), Length(min=8)], render_kw={
        'placeholder': trans('auth_password_placeholder', default='Enter a secure password'),
        'title': trans('auth_password_tooltip', default='At least 8 characters')
    })
    confirm_password = PasswordField(validators=[DataRequired(), EqualTo('password')], render_kw={
        'placeholder': trans('auth_confirm_password_placeholder', default='Confirm your password'),
        'title': trans('auth_confirm_password_tooltip', default='Re-enter your password')
    })
    submit = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username.label.text = trans('auth_username', default='Username', lang=lang)
        self.email.label.text = trans('core_email', default='Email', lang=lang)
        self.password.label.text = trans('auth_password', default='Password', lang=lang)
        self.confirm_password.label.text = trans('auth_confirm_password', default='Confirm Password', lang=lang)
        self.submit.label.text = trans('auth_signup', default='Sign Up', lang=lang)

    def validate_username(self, username):
        if mongo.db.users.find_one({'username': username.data}):
            raise ValidationError(trans('auth_username_taken', default='Username is already taken.'))

    def validate_email(self, email):
        if get_user_by_email(mongo, email.data):
            raise ValidationError(trans('auth_email_taken', default='Email is already registered.'))

class SigninForm(FlaskForm):
    email = StringField(validators=[DataRequired(), Email()], render_kw={
        'placeholder': trans('core_email_placeholder', default='e.g., user@example.com'),
        'title': trans('core_email_tooltip', default='Enter your email address')
    })
    password = PasswordField(validators=[DataRequired()], render_kw={
        'placeholder': trans('auth_password_placeholder', default='Enter your password'),
        'title': trans('auth_password_tooltip', default='Enter your password')
    })
    submit = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.email.label.text = trans('core_email', default='Email', lang=lang)
        self.password.label.text = trans('auth_password', default='Password', lang=lang)
        self.submit.label.text = trans('auth_signin', default='Sign In', lang=lang)

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(validators=[DataRequired()], render_kw={
        'placeholder': trans('auth_current_password_placeholder', default='Enter your current password'),
        'title': trans('auth_current_password', default='Enter your current password')
    })
    new_password = PasswordField(validators=[DataRequired(), Length(min=8)], render_kw={
        'placeholder': trans('auth_new_password_placeholder', default='Enter a new secure password'),
        'title': trans('auth_new_password', default='At least 8 characters')
    })
    confirm_new_password = PasswordField(validators=[DataRequired(), EqualTo('new_password')], render_kw={
        'placeholder': trans('auth_confirm_new_password', default='Confirm your new password'),
        'title': trans('auth_confirm_new_password', default='Confirm your new password')
    })
    submit = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_password.label.text = trans('auth_current_password', default='Current Password', lang=lang)
        self.new_password.label.text = trans('auth_new_password', default='New Password', lang=lang)
        self.confirm_new_password.label.text = trans('auth_confirm_new_password', default='Confirm New Password', lang=lang)
        self.submit.label.text = trans('auth_change_password', default='Change Password', lang=lang)

    def validate_current_password(self, current_password):
        if not check_password_hash(current_user.password_hash, current_password.data):
            raise ValidationError(trans('auth_invalid_current_password', default='Current password is incorrect.'))

class ForgotPasswordForm(FlaskForm):
    email = StringField(validators=[DataRequired(), Email()], render_kw={
        'placeholder': trans('core_email_placeholder', default='e.g., user@example.com'),
        'title': trans('core_email_tooltip', default='Enter your email address')
    })
    submit = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.email.label.text = trans('core_email', default='Email', lang=lang)
        self.submit.label.text = trans('core_submit', default='Submit', lang=lang)

class ResetPasswordForm(FlaskForm):
    new_password = PasswordField(validators=[DataRequired(), Length(min=8)], render_kw={
        'placeholder': trans('auth_new_password_placeholder', default='Enter a new secure password'),
        'title': trans('auth_new_password', default='At least 8 characters')
    })
    confirm_new_password = PasswordField(validators=[DataRequired(), EqualTo('new_password')], render_kw={
        'placeholder': trans('auth_confirm_new_password', default='Confirm your new password'),
        'title': trans('auth_confirm_new_password', default='Confirm your new password')
    })
    submit = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.new_password.label.text = trans('auth_new_password', default='New Password', lang=lang)
        self.confirm_new_password.label.text = trans('auth_confirm_new_password', default='Confirm New Password', lang=lang)
        self.submit.label.text = trans('core_submit', default='Submit', lang=lang)

# Routes
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    lang = session.get('lang', 'en')
    form = SignupForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    referral_code = request.args.get('ref')
    referrer = None
    session_id = session.get('sid', session.sid)
    session['sid'] = session_id
    
    # Log signup page view
    log_tool_usage(mongo, 'register', user_id=None, session_id=session_id, action='view_page')

    if referral_code:
        try:
            uuid.UUID(referral_code)
            referrer = mongo.db.users.find_one({'referral_code': referral_code}, {'_id': 0})
            if not referrer:
                logger.warning(f"Invalid referral code: {referral_code}", extra={'session_id': session_id})
                flash(trans('auth_invalid_referral', default='Invalid referral code.', lang=lang), 'warning')
            else:
                if not isinstance(referrer, dict):
                    logger.error(f"Referrer is not a dictionary: {type(referrer)}", extra={'session_id': session_id})
                    referrer = None
                else:
                    referral_count = mongo.db.users.count_documents({'referred_by_id': referrer.get('id')})
                    if referral_count >= 100:
                        logger.warning(f"Referral limit reached for referrer with code: {referral_code}", extra={'session_id': session_id})
                        flash(trans('auth_referral_limit_reached', default='This user has reached their referral limit.', lang=lang), 'warning')
                        referrer = None
        except ValueError:
            logger.error(f"Invalid referral code format: {referral_code}", extra={'session_id': session_id})
            flash(trans('auth_invalid_referral_format', default='Invalid referral code format.', lang=lang), 'warning')
    
    try:
        if request.method == 'POST':
            if form.validate_on_submit():
                is_admin = form.email.data == os.environ.get('ADMIN_EMAIL', 'abume@example.com')
                role = 'admin' if is_admin else 'user'
                user_data = {
                    'username': form.username.data,
                    'email': form.email.data,
                    'password_hash': generate_password_hash(form.password.data),
                    'is_admin': is_admin,
                    'role': role,
                    'referred_by_id': referrer.get('id') if referrer else None,
                    'created_at': datetime.utcnow(),
                    'lang': lang
                }
                user = create_user(mongo, user_data)
                username = getattr(user, 'username', 'unknown') if user else 'unknown'
                user_id = getattr(user, 'id', None) if user else None
                logger.info(f"User signed up: {username} with referral code: {user_data.get('referral_code', 'none')}, role={role}, is_admin={is_admin}", extra={'session_id': session_id})
                log_tool_usage(mongo, 'register', user_id=user_id, session_id=session_id, action='submit_success')
                flash(trans('auth_signup_success', default='Account created successfully! Please sign in.', lang=lang), 'success')
                return redirect(url_for('auth.signin'))
            else:
                logger.error(f"Signup form validation failed: {form.errors}", extra={'session_id': session_id, 'username': form.username.data, 'email': form.email.data})
                log_tool_usage(mongo, 'register', user_id=None, session_id=session_id, action='submit_error', details=f"Validation errors: {form.errors}")
                flash(trans('auth_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
        
        return render_template('signup.html', form=form, lang=lang, referral_code=referral_code, referrer=referrer)
    except Exception as e:
        logger.exception(f"Error in signup: {str(e)} - Type: {type(e).__name__}", extra={'session_id': session_id, 'username': form.username.data if form.username.data else 'unknown', 'email': form.email.data if form.email.data else 'unknown'})
        log_tool_usage(mongo, 'register', user_id=None, session_id=session_id, action='error', details=f"Exception: {str(e)} - Type: {type(e).__name__}")
        flash(trans('auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('signup.html', form=form, lang=lang, referral_code=referral_code, referrer=referrer), 500
    finally:
        logger.info("Teardown completed for signup route", extra={'session_id': session_id})

@auth_bp.route('/signin', methods=['GET', 'POST'])
def signin():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    lang = session.get('lang', 'en')
    form = SigninForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    session_id = session.get('sid', session.sid)
    session['sid'] = session_id
    
    # Log signin page view
    log_tool_usage(mongo, 'login', user_id=None, session_id=session_id, action='view_page')

    try:
        if request.method == 'POST' and form.validate_on_submit():
            user = get_user_by_email(mongo, form.email.data)
            if user and check_password_hash(getattr(user, 'password_hash', ''), form.password.data):
                logger.info(f"User object: id={getattr(user, 'id', None)}, username={getattr(user, 'username', None)}", extra={'session_id': session_id})
                login_user(user)
                session.modified = True
                username = getattr(user, 'username', 'unknown') if user else 'unknown'
                user_id = getattr(user, 'id', None) if user else None
                logger.info(f"User signed in: {username}, user_id: {user_id}, session: {dict(session)}", extra={'session_id': session_id})
                log_tool_usage(mongo, 'login', user_id=user_id, session_id=session_id, action='submit_success')
                flash(trans('auth_signin_success', default='Signed in successfully!', lang=lang), 'success')
                return redirect(url_for('index'))
            else:
                logger.warning(f"Invalid signin attempt for email: {form.email.data}", extra={'session_id': session_id})
                log_tool_usage(mongo, 'login', user_id=None, session_id=session_id, action='submit_error')
                flash(trans('auth_invalid_credentials', default='Invalid email or password.', lang=lang), 'danger')
        elif form.errors:
            logger.error(f"Signin form validation failed: {form.errors}", extra={'session_id': session_id})
            log_tool_usage(mongo, 'login', user_id=None, session_id=session_id, action='submit_error')
            flash(trans('auth_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
    
        return render_template('signin.html', form=form, lang=lang)
    except Exception as e:
        logger.exception(f"Error in signin: {str(e)} - Type: {type(e).__name__}", extra={'session_id': session_id})
        log_tool_usage(mongo, 'login', user_id=None, session_id=session_id, action='error', details=f"Exception: {str(e)} - Type: {type(e).__name__}")
        flash(trans('auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('signin.html', form=form, lang=lang), 500
    finally:
        logger.info("Teardown completed for signin route", extra={'session_id': session_id})

@auth_bp.route('/anonymous')
def anonymous():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    lang = session.get('lang', 'en')
    session_id = session.get('sid', session.sid)
    session['sid'] = session_id
    
    # Log anonymous access attempt
    log_tool_usage(mongo, 'anonymous_access', user_id=None, session_id=session_id, action='initiate')
    
    try:
        create_anonymous_session()
        logger.info(f"Anonymous access granted, session: {session_id}", extra={'session_id': session_id})
        log_tool_usage(mongo, 'anonymous_access', user_id=None, session_id=session_id, action='submit_success')
        next_url = request.args.get('next', url_for('general_dashboard'))
        return redirect(next_url)
    except Exception as e:
        logger.exception(f"Error in anonymous access: {str(e)} - Type: {type(e).__name__}", extra={'session_id': session_id})
        log_tool_usage(mongo, 'anonymous_access', user_id=None, session_id=session_id, action='error', details=f"Exception: {str(e)} - Type: {type(e).__name__}")
        flash(trans('auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return redirect(url_for('auth.signin')), 500
    finally:
        logger.info("Teardown completed for anonymous route", extra={'session_id': session_id})

@auth_bp.route('/logout')
@login_required
def logout():
    lang = session.get('lang', 'en')
    username = getattr(current_user, 'username', 'unknown') if current_user else 'unknown'
    user_id = getattr(current_user, 'id', None) if current_user else None
    session_id = session.get('sid', session.sid)
    
    # Log logout action
    log_tool_usage(mongo, 'logout', user_id=user_id, session_id=session_id, action='submit')
    
    logout_user()
    logger.info(f"User logged out: {username}", extra={'session_id': session_id})
    flash(trans('auth_logout_success', default='Logged out successfully!', lang=lang), 'success')
    return redirect(url_for('index'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    lang = session.get('lang', 'en')
    password_form = ChangePasswordForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    session_id = session.get('sid', session.sid)
    
    try:
        if request.method == 'POST' and password_form.validate_on_submit():
            update_user(mongo, getattr(current_user, 'id', None), {
                'password_hash': generate_password_hash(password_form.new_password.data)
            })
            username = getattr(current_user, 'username', 'unknown') if current_user else 'unknown'
            logger.info(f"User changed password: {username}", extra={'session_id': session_id})
            flash(trans('core_password_changed_success', default='Password changed successfully!', lang=lang), 'success')
            return redirect(url_for('auth.profile'))
        elif password_form.errors:
            logger.error(f"Change password form validation failed: {password_form.errors}", extra={'session_id': session_id})
            flash(trans('core_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
        
        referral_code = getattr(current_user, 'referral_code', None) if current_user else None
        referral_link = url_for('auth.signup', ref=referral_code, _external=True)
        referred_users = get_referrals(mongo, getattr(current_user, 'id', None))
        referral_count = len(referred_users)
        return render_template('profile.html', lang=lang, referral_link=referral_link, referral_count=referral_count, referred_users=referred_users, password_form=password_form)
    except Exception as e:
        logger.exception(f"Error in profile: {str(e)} - Type: {type(e).__name__}", extra={'session_id': session_id})
        flash(trans('core_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        referral_code = getattr(current_user, 'referral_code', None) if current_user else None
        referral_link = url_for('auth.signup', ref=referral_code, _external=True)
        referred_users = []
        referral_count = 0
        return render_template('profile.html', lang=lang, referral_link=referral_link, referral_count=referral_count, referred_users=referred_users, password_form=password_form), 500
    finally:
        logger.info("Teardown completed for profile route", extra={'session_id': session_id})

@auth_bp.route('/debug/auth')
def debug_auth():
    session_id = session.get('sid', session.sid)
    try:
        return jsonify({
            'is_authenticated': current_user.is_authenticated,
            'is_admin': getattr(current_user, 'id', None) if current_user.is_authenticated else False,
            'role': getattr(current_user, 'role', None) if current_user.is_authenticated else None,
            'email': getattr(current_user, 'email', None) if current_user.is_authenticated else None,
            'username': getattr(current_user, 'username', None) if current_user.is_authenticated else None,
            'session_id': session_id
        })
    except Exception as e:
        logger.exception(f"Error in debug_auth: {str(e)} - Type: {type(e).__name__}", extra={'session_id': session_id})
        return jsonify({'error': str(e)}), 500
    finally:
        logger.info("Teardown completed for debug_auth route", extra={'session_id': session_id})

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    lang = session.get('lang', 'en')
    form = ForgotPasswordForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    session_id = session.get('sid', session.sid)
    session['sid'] = session_id
    
    # Log forgot password page view
    log_tool_usage(mongo, 'forgot_password', user_id=None, session_id=session_id, action='view_page')
    
    try:
        if request.method == 'POST' and form.validate_on_submit():
            user = get_user_by_email(mongo, form.email.data)
            if user:
                serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
                token = serializer.dumps(form.email.data, salt='password-reset')
                mongo.db.reset_tokens.insert_one({
                    'user_id': user.id,
                    'token': token,
                    'created_at': datetime.utcnow(),
                    'expires_at': datetime.utcnow() + timedelta(hours=1)
                })
                send_reset_email(form.email.data, token)
                logger.info(f"Password reset email sent to: {form.email.data}", extra={'session_id': session_id})
                log_tool_usage(mongo, 'forgot_password', user_id=user.id, session_id=session_id, action='submit_success')
                flash(trans('core_reset_email_sent', default='A password reset link has been sent to your email.', lang=lang), 'success')
                return redirect(url_for('auth.signin'))
            else:
                logger.warning(f"No account found for email: {form.email.data}", extra={'session_id': session_id})
                log_tool_usage(mongo, 'forgot_password', user_id=None, session_id=session_id, action='submit_error')
                flash(trans('core_email_not_found', default='No account found with that email.', lang=lang), 'danger')
        elif form.errors:
            logger.error(f"Forgot password form validation failed: {form.errors}", extra={'session_id': session_id})
            log_tool_usage(mongo, 'forgot_password', user_id=None, session_id=session_id, action='submit_error')
            flash(trans('auth_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
        
        return render_template('forgot_password.html', form=form, lang=lang)
    except Exception as e:
        logger.exception(f"Error in forgot_password: {str(e)} - Type: {type(e).__name__}", extra={'session_id': session_id})
        log_tool_usage(mongo, 'forgot_password', user_id=None, session_id=session_id, action='error', details=f"Exception: {str(e)} - Type: {type(e).__name__}")
        flash(trans('auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('forgot_password.html', form=form, lang=lang), 500
    finally:
        logger.info("Teardown completed for forgot_password route", extra={'session_id': session_id})

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    lang = session.get('lang', 'en')
    form = ResetPasswordForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    session_id = session.get('sid', session.sid)
    session['sid'] = session_id
    
    # Log reset password page view
    log_tool_usage(mongo, 'reset_password', user_id=None, session_id=session_id, action='view_page')
    
    try:
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        email = serializer.loads(token, salt='password-reset', max_age=3600)
        token_doc = mongo.db.reset_tokens.find_one({'token': token})
        if not token_doc or token_doc['expires_at'] < datetime.utcnow():
            logger.warning(f"Invalid or expired token: {token}", extra={'session_id': session_id})
            log_tool_usage(mongo, 'reset_password', user_id=None, session_id=session_id, action='submit_error')
            flash(trans('core_invalid_or_expired_token', default='The reset link is invalid or has expired.', lang=lang), 'danger')
            return redirect(url_for('auth.signin'))
        
        if request.method == 'POST' and form.validate_on_submit():
            user = get_user_by_email(mongo, email)
            if user:
                update_user(mongo, user.id, {
                    'password_hash': generate_password_hash(form.new_password.data)
                })
                mongo.db.reset_tokens.delete_one({'token': token})
                logger.info(f"Password reset for user: {user.email}", extra={'session_id': session_id})
                log_tool_usage(mongo, 'reset_password', user_id=user.id, session_id=session_id, action='submit_success')
                flash(trans('core_password_reset_success', default='Your password has been reset successfully.', lang=lang), 'success')
                return redirect(url_for('auth.signin'))
            else:
                logger.error(f"User not found for email: {email}", extra={'session_id': session_id})
                log_tool_usage(mongo, 'reset_password', user_id=None, session_id=session_id, action='submit_error')
                flash(trans('core_email_not_found', default='No account found with that email.', lang=lang), 'danger')
                return redirect(url_for('auth.signin'))
        elif form.errors:
            logger.error(f"Reset password form validation failed: {form.errors}", extra={'session_id': session_id})
            log_tool_usage(mongo, 'reset_password', user_id=None, session_id=session_id, action='submit_error')
            flash(trans('auth_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
        
        return render_template('reset_password.html', form=form, lang=lang, token=token)
    except (SignatureExpired, BadSignature):
        logger.warning(f"Invalid or expired token: {token}", extra={'session_id': session_id})
        log_tool_usage(mongo, 'reset_password', user_id=None, session_id=session_id, action='submit_error')
        flash(trans('core_invalid_or_expired_token', default='The reset link is invalid or has expired.', lang=lang), 'danger')
        return redirect(url_for('auth.signin'))
    except Exception as e:
        logger.exception(f"Error in reset_password: {str(e)} - Type: {type(e).__name__}", extra={'session_id': session_id})
        log_tool_usage(mongo, 'reset_password', user_id=None, session_id=session_id, action='error', details=f"Exception: {str(e)} - Type: {type(e).__name__}")
        flash(trans('auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('reset_password.html', form=form, lang=lang, token=token), 500
    finally:
        logger.info("Teardown completed for reset_password route", extra={'session_id': session_id})

@auth_bp.route('/google-login')
def google_login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    session_id = session.get('sid', session.sid)
    session['sid'] = session_id
    lang = session.get('lang', 'en')
    
    # Log Google login initiation
    log_tool_usage(mongo, 'google_login', user_id=None, session_id=session_id, action='initiate')
    
    try:
        flow = Flow.from_client_config(
            {
                'web': {
                    'client_id': current_app.config['GOOGLE_CLIENT_ID'],
                    'client_secret': current_app.config['GOOGLE_CLIENT_SECRET'],
                    'redirect_uris': [url_for('auth.google_callback', _external=True)],
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token'
                }
            },
            scopes=['openid', 'email', 'profile']
        )

        logger.info(f"[AUTH_DEBUG] flow.redirect_uri before authorization_url call: {flow.redirect_uri}", extra={'session_id': session_id})
        resolved_url_for = url_for('auth.google_callback', _external=True)
        logger.info(f"[AUTH_DEBUG] url_for('auth.google_callback', _external=True) resolved to: {resolved_url_for}", extra={'session_id': session_id})

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        session['google_state'] = state
        logger.info(f"[AUTH_DEBUG] Generated Google OAuth2 authorization_url: {authorization_url}", extra={'session_id': session_id})
        return redirect(authorization_url)
    except Exception as e:
        logger.exception(f"Error in google_login: {str(e)} - Type: {type(e).__name__}", extra={'session_id': session_id})
        log_tool_usage(mongo, 'google_login', user_id=None, session_id=session_id, action='error', details=f"Exception: {str(e)} - Type: {type(e).__name__}")
        flash(trans('auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return redirect(url_for('auth.signin')), 500
    finally:
        logger.info("Teardown completed for google_login route", extra={'session_id': session_id})

@auth_bp.route('/google-callback')
def google_callback():
    session_id = session.get('sid', session.sid)
    session['sid'] = session_id
    lang = session.get('lang', 'en')
    
    # Log Google callback
    log_tool_usage(mongo, 'google_login', user_id=None, session_id=session_id, action='callback')
    
    try:
        state = session.get('google_state')
        if request.args.get('state') != state:
            logger.error(f"Invalid Google OAuth2 state parameter", extra={'session_id': session_id})
            log_tool_usage(mongo, 'google_login', user_id=None, session_id=session_id, action='error', details="Invalid state parameter")
            flash(trans('core_invalid_state', default='Invalid state parameter. Please try again.', lang=lang), 'danger')
            return redirect(url_for('auth.signin'))
        
        flow = Flow.from_client_config(
            {
                'web': {
                    'client_id': current_app.config['GOOGLE_CLIENT_ID'],
                    'client_secret': current_app.config['GOOGLE_CLIENT_SECRET'],
                    'redirect_uris': [url_for('auth.google_callback', _external=True)],
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token'
                }
            },
            scopes=['openid', 'email', 'profile'],
            state=state
        )
        flow.fetch_token(authorization_response=request.url)
        id_info = id_token.verify_oauth2_token(
            flow.credentials.id_token,
            google_requests.Request(),
            current_app.config['GOOGLE_CLIENT_ID']
        )
        google_id = id_info['sub']
        email = id_info['email']
        username = email.split('@')[0]  # Derive username from email
        
        user = mongo.db.users.find_one({'google_id': google_id})
        if not user:
            user = get_user_by_email(mongo, email)
            if user:
                mongo.db.users.update_one(
                    {'_id': user._id},
                    {'$set': {'google_id': google_id}}
                )
                user = get_user(mongo, str(user._id))
            else:
                user_data = {
                    'username': username,
                    'email': email,
                    'google_id': google_id,
                    'password_hash': None,
                    'is_admin': False,
                    'role': 'user',
                    'created_at': datetime.utcnow(),
                    'lang': lang
                }
                user = create_user(mongo, user_data)
        
        login_user(user)
        session.modified = True
        logger.info(f"User signed in via Google: {user.email}, user_id: {user.id}, session: {dict(session)}", extra={'session_id': session_id})
        log_tool_usage(mongo, 'google_login', user_id=user.id, session_id=session_id, action='submit_success')
        flash(trans('core_google_login_success', default='Successfully logged in with Google.', lang=lang), 'success')
        return redirect(url_for('index'))
    except Exception as e:
        logger.exception(f"Error in google_callback: {str(e)} - Type: {type(e).__name__}", extra={'session_id': session_id})
        log_tool_usage(mongo, 'google_login', user_id=None, session_id=session_id, action='error', details=f"Exception: {str(e)} - Type: {type(e).__name__}")
        flash(trans('auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return redirect(url_for('auth.signin')), 500
    finally:
        logger.info("Teardown completed for google_callback route", extra={'session_id': session_id})

def send_reset_email(email, token):
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    msg = MIMEText(f"Click this link to reset your password: {reset_url}\nThis link will expire in 1 hour.")
    msg['Subject'] = trans('core_reset_email_subject', default='Password Reset Request')
    msg['From'] = current_app.config['SMTP_USERNAME']
    msg['To'] = email
    try:
        with smtplib.SMTP(current_app.config['SMTP_SERVER'], current_app.config['SMTP_PORT']) as server:
            server.starttls()
            server.login(current_app.config['SMTP_USERNAME'], current_app.config['SMTP_PASSWORD'])
            server.send_message(msg)
    except Exception as e:
        logger.error(f"Failed to send reset email to {email}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        raise
