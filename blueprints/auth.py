from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from translations import trans
from extensions import db
from models import User
import logging

# Configure logging
logger = logging.getLogger('ficore_app')

# Define the auth blueprint
auth_bp = Blueprint('auth', __name__, template_folder='templates', url_prefix='/auth')

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
        if User.query.filter_by(username=username.data).first():
            raise ValidationError(trans('auth_username_taken', default='Username is already taken.'))

    def validate_email(self, email):
        if User.query.filter_by(email=email.data).first():
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

# Routes
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    lang = session.get('lang', 'en')
    form = SignupForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    
    try:
        if request.method == 'POST' and form.validate_on_submit():
            user = User(
                username=form.username.data,
                email=form.email.data,
                password_hash=generate_password_hash(form.password.data)
            )
            db.session.add(user)
            db.session.commit()
            logger.info(f"User signed up: {user.username}", extra={'session_id': session.get('sid', 'unknown')})
            flash(trans('auth_signup_success', default='Account created successfully! Please sign in.', lang=lang), 'success')
            return redirect(url_for('auth.signin'))
        elif form.errors:
            logger.error(f"Signup form validation failed: {form.errors}", extra={'session_id': session.get('sid', 'unknown')})
            flash(trans('auth_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
        
        return render_template('signup.html', form=form, lang=lang)
    except Exception as e:
        logger.error(f"Error in signup: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        flash(trans('auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('signup.html', form=form, lang=lang), 500

@auth_bp.route('/signin', methods=['GET', 'POST'])
def signin():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    lang = session.get('lang', 'en')
    form = SigninForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    
    try:
        if request.method == 'POST' and form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user)
                logger.info(f"User signed in: {user.username}", extra={'session_id': session.get('sid', 'unknown')})
                flash(trans('auth_signin_success', default='Signed in successfully!', lang=lang), 'success')
                return redirect(url_for('index'))
            else:
                logger.warning(f"Invalid signin attempt for email: {form.email.data}", extra={'session_id': session.get('sid', 'unknown')})
                flash(trans('auth_invalid_credentials', default='Invalid email or password.', lang=lang), 'danger')
        
        elif form.errors:
            logger.error(f"Signin form validation failed: {form.errors}", extra={'session_id': session.get('sid', 'unknown')})
            flash(trans('auth_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
        
        return render_template('signin.html', form=form, lang=lang)
    except Exception as e:
        logger.error(f"Error in signin: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        flash(trans('auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('signin.html', form=form, lang=lang), 500

@auth_bp.route('/logout')
@login_required
def logout():
    lang = session.get('lang', 'en')
    username = current_user.username
    logout_user()
    logger.info(f"User logged out: {username}", extra={'session_id': session.get('sid', 'unknown')})
    flash(trans('auth_logout_success', default='Logged out successfully!', lang=lang), 'success')
    return redirect(url_for('index'))
