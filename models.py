import uuid
from datetime import datetime, date
import json
from flask import current_app, session
from flask_login import UserMixin

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['id'])  # Ensure ID is a string for Flask-Login
        self.username = user_data['username']
        self.email = user_data['email']
        self.password_hash = user_data['password_hash']
        self.created_at = user_data['created_at']
        self.lang = user_data['lang']
        self.referral_code = user_data['referral_code']
        self.is_admin = user_data['is_admin']
        self.role = user_data['role']
        self.referred_by_id = user_data.get('referred_by_id')
        self.google_id = user_data.get('google_id')  # Added for Google OAuth2

    def get_id(self):
        return self.id  # Flask-Login expects a string

# User helper functions
def create_user(mongo, user_data):
    """Create a new user in the users collection."""
    required_fields = ['username', 'email', 'password_hash']
    for field in required_fields:
        if field not in user_data or user_data[field] is None:
            raise ValueError(f"Missing required field: {field}")
    user = {
        'id': user_data.get('id', int(uuid.uuid4().int % 10000000000)),  # Integer ID
        'username': user_data['username'],
        'email': user_data['email'],
        'password_hash': user_data['password_hash'],
        'created_at': user_data.get('created_at', datetime.utcnow()),
        'lang': user_data.get('lang', 'en'),
        'referral_code': user_data.get('referral_code', str(uuid.uuid4())),
        'is_admin': user_data.get('is_admin', False),
        'role': user_data.get('role', 'user'),
        'referred_by_id': user_data.get('referred_by_id'),
        'google_id': user_data.get('google_id')  # Added for Google OAuth2
    }
    try:
        mongo.db.users.insert_one(user)
        return User(user)
    except Exception as e:
        current_app.logger.error(f"Failed to create user: {str(e)}", extra={'user_data': user_data})
        raise

def get_user(mongo, user_id):
    """Retrieve a user by ID."""
    try:
        # Try querying as integer first
        user = mongo.db.users.find_one({'id': int(user_id)}, {'_id': 0})
        if user:
            return User(user)
        # Fallback to string query
        user = mongo.db.users.find_one({'id': str(user_id)}, {'_id': 0})
        if user:
            return User(user)
        current_app.logger.warning(f"No user found for id: {user_id}")
        return None
    except ValueError:
        current_app.logger.error(f"Invalid user_id format: {user_id}")
        return None
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve user {user_id}: {str(e)}")
        return None

def get_user_by_email(mongo, email):
    """Retrieve a user by email."""
    user = mongo.db.users.find_one({'email': email}, {'_id': 0})
    if user:
        return User(user)
    return None

def update_user(mongo, user_id, updates):
    """Update user fields."""
    try:
        result = mongo.db.users.update_one({'id': int(user_id)}, {'$set': updates})
        if result.matched_count == 0:
            result = mongo.db.users.update_one({'id': str(user_id)}, {'$set': updates})
            if result.matched_count == 0:
                current_app.logger.warning(f"No user found for id: {user_id}")
                return False
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to update user {user_id}: {str(e)}", extra={'updates': updates})
        raise

def get_referrals(mongo, user_id):
    """Retrieve users referred by the given user ID."""
    referrals = mongo.db.users.find({'referred_by_id': str(user_id)}, {'_id': 0})
    return [User(r) for r in referrals]

def create_reset_token(mongo, token_data):
    """Create a reset token in the reset_tokens collection."""
    required_fields = ['user_id', 'token', 'expires_at']
    for field in required_fields:
        if field not in token_data or token_data[field] is None:
            raise ValueError(f"Missing required field: {field}")
    reset_token = {
        'user_id': token_data['user_id'],
        'token': token_data['token'],
        'created_at': token_data.get('created_at', datetime.utcnow()),
        'expires_at': token_data['expires_at']
    }
    try:
        mongo.db.reset_tokens.insert_one(reset_token)
        return reset_token
    except Exception as e:
        current_app.logger.error(f"Failed to create reset token: {str(e)}", extra={'token_data': token_data})
        raise

def get_reset_token(mongo, token):
    """Retrieve a reset token by token string."""
    return mongo.db.reset_tokens.find_one({'token': token}, {'_id': 0})

def delete_reset_token(mongo, token):
    """Delete a reset token by token string."""
    try:
        mongo.db.reset_tokens.delete_one({'token': token})
    except Exception as e:
        current_app.logger.error(f"Failed to delete reset token: {str(e)}", extra={'token': token})
        raise

# Course helper functions
def create_course(mongo, course_data):
    """Create a new course in the courses collection."""
    required_fields = ['id', 'title_key', 'title_en', 'title_ha', 'description_en', 'description_ha']
    for field in required_fields:
        if field not in course_data or course_data[field] is None:
            raise ValueError(f"Missing required field: {field}")
    course = {
        'id': str(course_data['id']),  # Ensure string ID
        'title_key': course_data['title_key'],
        'title_en': course_data['title_en'],
        'title_ha': course_data['title_ha'],
        'description_en': course_data['description_en'],
        'description_ha': course_data['description_ha'],
        'is_premium': course_data.get('is_premium', False),
        'created_at': course_data.get('created_at', datetime.utcnow())
    }
    try:
        mongo.db.courses.insert_one(course)
        return course
    except Exception as e:
        current_app.logger.error(f"Failed to create course: {str(e)}", extra={'course_data': course_data})
        raise

def get_course(mongo, course_id):
    """Retrieve a course by ID."""
    return mongo.db.courses.find_one({'id': str(course_id)}, {'_id': 0})

def get_all_courses(mongo):
    """Retrieve all courses."""
    return list(mongo.db.courses.find({}, {'_id': 0}))

def to_dict_course(course):
    """Convert course document to dict."""
    return {
        'id': course.get('id', None),
        'title_key': course.get('title_key', ''),
        'title_en': course.get('title_en', ''),
        'title_ha': course.get('title_ha', ''),
        'description_en': course.get('description_en', ''),
        'description_ha': course.get('description_ha', ''),
        'is_premium': course.get('is_premium', False),
        'created_at': (course['created_at'].isoformat() + "Z") if isinstance(course.get('created_at'), datetime) else course.get('created_at', '')
    }

# ContentMetadata helper functions
def create_content_metadata(mongo, metadata):
    """Create content metadata."""
    required_fields = ['course_id', 'lesson_id', 'content_type', 'content_path']
    for field in required_fields:
        if field not in metadata or metadata[field] is None:
            raise ValueError(f"Missing required field: {field}")
    metadata_doc = {
        'id': str(uuid.uuid4()),  # String UUID
        'course_id': metadata['course_id'],
        'lesson_id': metadata['lesson_id'],
        'content_type': metadata['content_type'],
        'content_path': metadata['content_path'],
        'uploaded_by': metadata.get('uploaded_by'),
        'upload_date': metadata.get('upload_date', datetime.utcnow()),
        'created_at': metadata.get('created_at', datetime.utcnow())
    }
    try:
        mongo.db.content_metadata.insert_one(metadata_doc)
        return metadata_doc
    except Exception as e:
        current_app.logger.error(f"Failed to create content metadata: {str(e)}", extra={'metadata': metadata})
        raise

def get_content_metadata(mongo, metadata_id):
    """Retrieve content metadata by ID."""
    return mongo.db.content_metadata.find_one({'id': str(metadata_id)}, {'_id': 0})

# FinancialHealth helper functions
def create_financial_health(mongo, fh_data):
    """Create a financial health record."""
    required_fields = ['session_id']
    for field in required_fields:
        if field not in fh_data or fh_data[field] is None:
            raise ValueError(f"Missing required field: {field}")
    fh = {
        'id': str(uuid.uuid4()),
        'user_id': fh_data.get('user_id'),
        'session_id': fh_data['session_id'],
        'created_at': fh_data.get('created_at', datetime.utcnow()),
        'first_name': fh_data.get('first_name'),
        'email': fh_data.get('email'),
        'user_type': fh_data.get('user_type'),
        'send_email': fh_data.get('send_email', False),
        'income': fh_data.get('income'),
        'expenses': fh_data.get('expenses'),
        'debt': fh_data.get('debt'),
        'interest_rate': fh_data.get('interest_rate'),
        'debt_to_income': fh_data.get('debt_to_income'),
        'savings_rate': fh_data.get('savings_rate'),
        'interest_burden': fh_data.get('interest_burden'),
        'score': fh_data.get('score'),
        'status': fh_data.get('status'),
        'status_key': fh_data.get('status_key'),
        'badges': json.dumps(fh_data.get('badges', [])),
        'step': fh_data.get('step')
    }
    try:
        mongo.db.financial_health.insert_one(fh)
        return fh
    except Exception as e:
        current_app.logger.error(f"Failed to create financial health record: {str(e)}", extra={'fh_data': fh_data})
        raise

def get_financial_health(mongo, filters):
    """Retrieve financial health records by filters."""
    records = mongo.db.financial_health.find(filters, {'_id': 0}).sort('created_at', -1)
    valid_records = [r for r in records if 'id' in r]
    for r in records:
        if 'id' not in r:
            current_app.logger.warning(f"Skipping financial health record without 'id': {r}")
    return valid_records

def to_dict_financial_health(fh):
    """Convert financial health document to dict."""
    try:
        badges = json.loads(fh['badges']) if fh.get('badges') else []
    except json.JSONDecodeError:
        current_app.logger.error(f"Invalid JSON in badges for FinancialHealth ID {fh.get('id', 'unknown')}")
        badges = []
    return {
        'id': fh.get('id', None),
        'user_id': fh.get('user_id', None),
        'session_id': fh.get('session_id', None),
        'created_at': (fh['created_at'].isoformat() + "Z") if isinstance(fh.get('created_at'), datetime) else fh.get('created_at', ''),
        'first_name': fh.get('first_name', None),
        'email': fh.get('email', None),
        'user_type': fh.get('user_type', None),
        'send_email': fh.get('send_email', False),
        'income': fh.get('income', None),
        'expenses': fh.get('expenses', None),
        'debt': fh.get('debt', None),
        'interest_rate': fh.get('interest_rate', None),
        'debt_to_income': fh.get('debt_to_income', None),
        'savings_rate': fh.get('savings_rate', None),
        'interest_burden': fh.get('interest_burden', None),
        'score': fh.get('score', None),
        'status': fh.get('status', None),
        'status_key': fh.get('status_key', None),
        'badges': badges,
        'step': fh.get('step', None)
    }

# Budget helper functions
def create_budget(mongo, budget_data):
    """Create a budget record."""
    required_fields = ['session_id']
    for field in required_fields:
        if field not in budget_data or budget_data[field] is None:
            raise ValueError(f"Missing required field: {field}")
    budget = {
        'id': str(uuid.uuid4()),
        'user_id': budget_data.get('user_id'),
        'session_id': budget_data['session_id'],
        'created_at': budget_data.get('created_at', datetime.utcnow()),
        'user_email': budget_data.get('user_email'),
        'income': budget_data.get('income', 0.0),
        'fixed_expenses': budget_data.get('fixed_expenses', 0.0),
        'variable_expenses': budget_data.get('variable_expenses', 0.0),
        'savings_goal': budget_data.get('savings_goal', 0.0),
        'surplus_deficit': budget_data.get('surplus_deficit'),
        'housing': budget_data.get('housing', 0.0),
        'food': budget_data.get('food', 0.0),
        'transport': budget_data.get('transport', 0.0),
        'dependents': budget_data.get('dependents', 0.0),
        'miscellaneous': budget_data.get('miscellaneous', 0.0),
        'others': budget_data.get('others', 0.0)
    }
    try:
        mongo.db.budgets.insert_one(budget)
        return budget
    except Exception as e:
        current_app.logger.error(f"Failed to create budget record: {str(e)}", extra={'budget_data': budget_data})
        raise

def get_budgets(mongo, filters):
    """Retrieve budget records by filters."""
    records = mongo.db.budgets.find(filters, {'_id': 0}).sort('created_at', -1)
    valid_records = [r for r in records if 'id' in r]
    for r in records:
        if 'id' not in r:
            current_app.logger.warning(f"Skipping budget record without 'id': {r}")
    return valid_records

def to_dict_budget(budget):
    """Convert budget document to dict."""
    return {
        'id': budget.get('id', None),
        'user_id': budget.get('user_id', None),
        'session_id': budget.get('session_id', None),
        'created_at': (budget['created_at'].isoformat() + "Z") if isinstance(budget.get('created_at'), datetime) else budget.get('created_at', ''),
        'user_email': budget.get('user_email', None),
        'income': budget.get('income', 0.0),
        'fixed_expenses': budget.get('fixed_expenses', 0.0),
        'variable_expenses': budget.get('variable_expenses', 0.0),
        'savings_goal': budget.get('savings_goal', 0.0),
        'surplus_deficit': budget.get('surplus_deficit', None),
        'housing': budget.get('housing', 0.0),
        'food': budget.get('food', 0.0),
        'transport': budget.get('transport', 0.0),
        'dependents': budget.get('dependents', 0.0),
        'miscellaneous': budget.get('miscellaneous', 0.0),
        'others': budget.get('others', 0.0)
    }

# Bill helper functions
def create_bill(mongo, bill_data):
    """Create a bill record."""
    required_fields = ['session_id', 'bill_name', 'amount', 'due_date', 'frequency', 'category', 'status']
    for field in required_fields:
        if field not in bill_data or bill_data[field] is None:
            raise ValueError(f"Missing required field: {field}")
    bill = {
        'id': str(uuid.uuid4()),
        'user_id': bill_data.get('user_id'),
        'session_id': bill_data['session_id'],
        'created_at': bill_data.get('created_at', datetime.utcnow()),
        'user_email': bill_data.get('user_email'),
        'first_name': bill_data.get('first_name'),
        'bill_name': bill_data['bill_name'],
        'amount': bill_data['amount'],
        'due_date': bill_data['due_date'].strftime('%Y-%m-%d') if isinstance(bill_data['due_date'], date) else bill_data['due_date'],
        'frequency': bill_data['frequency'],
        'category': bill_data['category'],
        'status': bill_data['status'],
        'send_email': bill_data.get('send_email', False),
        'reminder_days': bill_data.get('reminder_days')
    }
    try:
        mongo.db.bills.insert_one(bill)
        return bill
    except Exception as e:
        current_app.logger.error(f"Failed to create bill record: {str(e)}", extra={'bill_data': bill_data})
        raise

def get_bills(mongo, filters):
    """Retrieve bill records by filters."""
    records = mongo.db.bills.find(filters, {'_id': 0})
    valid_records = [r for r in records if 'id' in r]
    for r in records:
        if 'id' not in r:
            current_app.logger.warning(f"Skipping bill record without 'id': {r}")
    return valid_records

def to_dict_bill(bill):
    """Convert bill document to dict."""
    return {
        'id': bill.get('id', None),
        'user_id': bill.get('user_id', None),
        'session_id': bill.get('session_id', None),
        'created_at': (bill['created_at'].isoformat() + "Z") if isinstance(bill.get('created_at'), datetime) else bill.get('created_at', ''),
        'user_email': bill.get('user_email', None),
        'first_name': bill.get('first_name', None),
        'bill_name': bill.get('bill_name', ''),
        'amount': bill.get('amount', 0.0),
        'due_date': bill.get('due_date', ''),
        'frequency': bill.get('frequency', ''),
        'category': bill.get('category', ''),
        'status': bill.get('status', ''),
        'send_email': bill.get('send_email', False),
        'reminder_days': bill.get('reminder_days', None)
    }

# NetWorth helper functions
def create_net_worth(mongo, nw_data):
    """Create a net worth record."""
    required_fields = ['session_id']
    for field in required_fields:
        if field not in nw_data or nw_data[field] is None:
            raise ValueError(f"Missing required field: {field}")
    nw = {
        'id': str(uuid.uuid4()),
        'user_id': nw_data.get('user_id'),
        'session_id': nw_data['session_id'],
        'created_at': nw_data.get('created_at', datetime.utcnow()),
        'first_name': nw_data.get('first_name'),
        'email': nw_data.get('email'),
        'send_email': nw_data.get('send_email', False),
        'cash_savings': nw_data.get('cash_savings'),
        'investments': nw_data.get('investments'),
        'property': nw_data.get('property'),
        'loans': nw_data.get('loans'),
        'total_assets': nw_data.get('total_assets'),
        'total_liabilities': nw_data.get('total_liabilities'),
        'net_worth': nw_data.get('net_worth'),
        'badges': json.dumps(nw_data.get('badges', []))
    }
    try:
        mongo.db.net_worth.insert_one(nw)
        return nw
    except Exception as e:
        current_app.logger.error(f"Failed to create net worth record: {str(e)}", extra={'nw_data': nw_data})
        raise

def get_net_worth(mongo, filters):
    """Retrieve net worth records by filters."""
    records = mongo.db.net_worth.find(filters, {'_id': 0}).sort('created_at', -1)
    valid_records = [r for r in records if 'id' in r]
    for r in records:
        if 'id' not in r:
            current_app.logger.warning(f"Skipping net worth record without 'id': {r}")
    return valid_records

def to_dict_net_worth(nw):
    """Convert net worth document to dict."""
    try:
        badges = json.loads(nw['badges']) if nw.get('badges') else []
    except json.JSONDecodeError:
        current_app.logger.error(f"Invalid JSON in badges for NetWorth ID {nw.get('id', 'unknown')}")
        badges = []
    return {
        'id': nw.get('id', None),
        'user_id': nw.get('user_id', None),
        'session_id': nw.get('session_id', None),
        'created_at': (nw['created_at'].isoformat() + "Z") if isinstance(nw.get('created_at'), datetime) else nw.get('created_at', ''),
        'first_name': nw.get('first_name', None),
        'email': nw.get('email', None),
        'send_email': nw.get('send_email', False),
        'cash_savings': nw.get('cash_savings', None),
        'investments': nw.get('investments', None),
        'property': nw.get('property', None),
        'loans': nw.get('loans', None),
        'total_assets': nw.get('total_assets', None),
        'total_liabilities': nw.get('total_liabilities', None),
        'net_worth': nw.get('net_worth', None),
        'badges': badges
    }

# EmergencyFund helper functions
def create_emergency_fund(mongo, ef_data):
    """Create an emergency fund record."""
    required_fields = ['session_id']
    for field in required_fields:
        if field not in ef_data or ef_data[field] is None:
            raise ValueError(f"Missing required field: {field}")
    ef = {
        'id': str(uuid.uuid4()),
        'user_id': ef_data.get('user_id'),
        'session_id': ef_data['session_id'],
        'created_at': ef_data.get('created_at', datetime.utcnow()),
        'first_name': ef_data.get('first_name'),
        'email': ef_data.get('email'),
        'email_opt_in': ef_data.get('email_opt_in', False),
        'lang': ef_data.get('lang'),
        'monthly_expenses': ef_data.get('monthly_expenses'),
        'monthly_income': ef_data.get('monthly_income'),
        'current_savings': ef_data.get('current_savings'),
        'risk_tolerance_level': ef_data.get('risk_tolerance_level'),
        'dependents': ef_data.get('dependents'),
        'timeline': ef_data.get('timeline'),
        'recommended_months': ef_data.get('recommended_months'),
        'target_amount': ef_data.get('target_amount'),
        'savings_gap': ef_data.get('savings_gap'),
        'monthly_savings': ef_data.get('monthly_savings'),
        'percent_of_income': ef_data.get('percent_of_income'),
        'badges': json.dumps(ef_data.get('badges', []))
    }
    try:
        mongo.db.emergency_funds.insert_one(ef)
        return ef
    except Exception as e:
        current_app.logger.error(f"Failed to create emergency fund record: {str(e)}", extra={'ef_data': ef_data})
        raise

def get_emergency_funds(mongo, filters):
    """Retrieve emergency fund records by filters."""
    records = mongo.db.emergency_funds.find(filters, {'_id': 0}).sort('created_at', -1)
    valid_records = [r for r in records if 'id' in r]
    for r in records:
        if 'id' not in r:
            current_app.logger.warning(f"Skipping emergency fund record without 'id': {r}")
    return valid_records

def to_dict_emergency_fund(ef):
    """Convert emergency fund document to dict."""
    try:
        badges = json.loads(ef['badges']) if ef.get('badges') else []
    except json.JSONDecodeError:
        current_app.logger.error(f"Invalid JSON in badges for EmergencyFund ID {ef.get('id', 'unknown')}")
        badges = []
    return {
        'id': ef.get('id', None),
        'user_id': ef.get('user_id', None),
        'session_id': ef.get('session_id', None),
        'created_at': (ef['created_at'].isoformat() + "Z") if isinstance(ef.get('created_at'), datetime) else ef.get('created_at', ''),
        'first_name': ef.get('first_name', None),
        'email': ef.get('email', None),
        'email_opt_in': ef.get('email_opt_in', False),
        'lang': ef.get('lang', None),
        'monthly_expenses': ef.get('monthly_expenses', None),
        'monthly_income': ef.get('monthly_income', None),
        'current_savings': ef.get('current_savings', None),
        'risk_tolerance_level': ef.get('risk_tolerance_level', None),
        'dependents': ef.get('dependents', None),
        'timeline': ef.get('timeline', None),
        'recommended_months': ef.get('recommended_months', None),
        'target_amount': ef.get('target_amount', None),
        'savings_gap': ef.get('savings_gap', None),
        'monthly_savings': ef.get('monthly_savings', None),
        'percent_of_income': ef.get('percent_of_income', None),
        'badges': badges
    }

# LearningProgress helper functions
def create_learning_progress(mongo, lp_data):
    """Create a learning progress record."""
    required_fields = ['session_id', 'course_id']
    for field in required_fields:
        if field not in lp_data or lp_data[field] is None:
            raise ValueError(f"Missing required field: {field}")
    lp = {
        'id': str(uuid.uuid4()),
        'user_id': lp_data.get('user_id'),
        'session_id': lp_data['session_id'],
        'course_id': lp_data['course_id'],
        'lessons_completed': json.dumps(lp_data.get('lessons_completed', [])),
        'quiz_scores': json.dumps(lp_data.get('quiz_scores', {})),
        'current_lesson': lp_data.get('current_lesson'),
        'created_at': lp_data.get('created_at', datetime.utcnow())
    }
    try:
        mongo.db.learning_progress.insert_one(lp)
        return lp
    except Exception as e:
        current_app.logger.error(f"Failed to create learning progress record: {str(e)}", extra={'lp_data': lp_data})
        raise

def get_learning_progress(mongo, filters):
    """Retrieve learning progress records by filters."""
    records = mongo.db.learning_progress.find(filters, {'_id': 0}).sort('created_at', -1)
    valid_records = [r for r in records if 'id' in r]
    for r in records:
        if 'id' not in r:
            current_app.logger.warning(f"Skipping learning progress record without 'id': {r}")
    return valid_records

def to_dict_learning_progress(lp):
    """Convert learning progress document to dict."""
    try:
        lessons_completed = json.loads(lp['lessons_completed']) if lp.get('lessons_completed') else []
        quiz_scores = json.loads(lp['quiz_scores']) if lp.get('quiz_scores') else {}
    except json.JSONDecodeError:
        current_app.logger.error(f"Invalid JSON in LearningProgress ID {lp.get('id', 'unknown')}")
        lessons_completed = []
        quiz_scores = {}
    return {
        'id': lp.get('id', None),
        'user_id': lp.get('user_id', None),
        'session_id': lp.get('session_id', None),
        'course_id': lp.get('course_id', None),
        'lessons_completed': lessons_completed,
        'quiz_scores': quiz_scores,
        'current_lesson': lp.get('current_lesson', None),
        'created_at': (lp['created_at'].isoformat() + "Z") if isinstance(lp.get('created_at'), datetime) else lp.get('created_at', '')
    }

# QuizResult helper functions
def create_quiz_result(mongo, qr_data):
    """Create a quiz result record."""
    required_fields = ['session_id']
    for field in required_fields:
        if field not in qr_data or qr_data[field] is None:
            raise ValueError(f"Missing required field: {field}")
    qr = {
        'id': str(uuid.uuid4()),
        'user_id': qr_data.get('user_id'),
        'session_id': qr_data['session_id'],
        'created_at': qr_data.get('created_at', datetime.utcnow()),
        'first_name': qr_data.get('first_name'),
        'email': qr_data.get('email'),
        'send_email': qr_data.get('send_email', False),
        'personality': qr_data.get('personality'),
        'score': qr_data.get('score'),
        'badges': json.dumps(qr_data.get('badges', [])),
        'insights': json.dumps(qr_data.get('insights', [])),
        'tips': json.dumps(qr_data.get('tips', []))
    }
    try:
        mongo.db.quiz_results.insert_one(qr)
        return qr
    except Exception as e:
        current_app.logger.error(f"Failed to create quiz result record: {str(e)}", extra={'qr_data': qr_data})
        raise

def get_quiz_results(mongo, filters):
    """Retrieve quiz result records by filters."""
    records = mongo.db.quiz_results.find(filters, {'_id': 0}).sort('created_at', -1)
    valid_records = [r for r in records if 'id' in r]
    for r in records:
        if 'id' not in r:
            current_app.logger.warning(f"Skipping quiz result record without 'id': {r}")
    return valid_records

def to_dict_quiz_result(qr):
    """Convert quiz result document to dict."""
    try:
        badges = json.loads(qr['badges']) if qr.get('badges') else []
        insights = json.loads(qr['insights']) if qr.get('insights') else []
        tips = json.loads(qr['tips']) if qr.get('tips') else []
    except json.JSONDecodeError:
        current_app.logger.error(f"Invalid JSON in QuizResult ID {qr.get('id', 'unknown')}")
        badges = []
        insights = []
        tips = []
    return {
        'id': qr.get('id', None),
        'user_id': qr.get('user_id', None),
        'session_id': qr.get('session_id', None),
        'created_at': (qr['created_at'].isoformat() + "Z") if isinstance(qr.get('created_at'), datetime) else qr.get('created_at', ''),
        'first_name': qr.get('first_name', None),
        'email': qr.get('email', None),
        'send_email': qr.get('send_email', False),
        'personality': qr.get('personality', None),
        'score': qr.get('score', None),
        'badges': badges,
        'insights': insights,
        'tips': tips
    }

# Feedback helper functions
def create_feedback(mongo, feedback_data):
    """Create a feedback record."""
    required_fields = ['session_id', 'tool_name', 'rating']
    for field in required_fields:
        if field not in feedback_data or feedback_data[field] is None:
            raise ValueError(f"Missing required field: {field}")
    feedback = {
        'id': str(uuid.uuid4()),
        'user_id': feedback_data.get('user_id'),
        'session_id': feedback_data['session_id'],
        'created_at': feedback_data.get('created_at', datetime.utcnow()),
        'tool_name': feedback_data['tool_name'],
        'rating': feedback_data['rating'],
        'comment': feedback_data.get('comment')
    }
    try:
        mongo.db.feedback.insert_one(feedback)
        return feedback
    except Exception as e:
        current_app.logger.error(f"Failed to create feedback record: {str(e)}", extra={'feedback_data': feedback_data})
        raise

def get_feedback(mongo, filters):
    """Retrieve feedback records by filters."""
    records = mongo.db.feedback.find(filters, {'_id': 0})
    valid_records = [r for r in records if 'id' in r]
    for r in records:
        if 'id' not in r:
            current_app.logger.warning(f"Skipping feedback record without 'id': {r}")
    return valid_records

def to_dict_feedback(feedback):
    """Convert feedback document to dict."""
    return {
        'id': feedback.get('id', None),
        'user_id': feedback.get('user_id', None),
        'session_id': feedback.get('session_id', None),
        'created_at': (feedback['created_at'].isoformat() + "Z") if isinstance(feedback.get('created_at'), datetime) else feedback.get('created_at', ''),
        'tool_name': feedback.get('tool_name', ''),
        'rating': feedback.get('rating', None),
        'comment': feedback.get('comment', None)
    }

# ToolUsage helper functions
def create_tool_usage(mongo, tool_usage_data):
    """Create a tool usage record."""
    required_fields = ['tool_name', 'session_id']
    for field in required_fields:
        if field not in tool_usage_data or tool_usage_data[field] is None:
            raise ValueError(f"Missing required field: {field}")
    tool_usage = {
        'id': str(uuid.uuid4()),
        'tool_name': tool_usage_data['tool_name'],
        'user_id': tool_usage_data.get('user_id'),
        'session_id': tool_usage_data['session_id'],
        'action': tool_usage_data.get('action', 'unknown'),
        'created_at': tool_usage_data.get('created_at', datetime.utcnow())
    }
    try:
        mongo.db.tool_usage.insert_one(tool_usage)
        return tool_usage
    except Exception as e:
        current_app.logger.error(f"Failed to create tool usage record: {str(e)}", extra={'tool_usage_data': tool_usage_data})
        raise

def get_tool_usage(mongo, filters):
    """Retrieve tool usage records by filters."""
    records = mongo.db.tool_usage.find(filters, {'_id': 0})
    valid_records = [r for r in records if 'id' in r]
    for r in records:
        if 'id' not in r:
            current_app.logger.warning(f"Skipping tool usage record without 'id': {r}")
    return valid_records

def to_dict_tool_usage(tu):
    """Convert tool usage document to dict."""
    return {
        'id': tu.get('id', None),
        'tool_name': tu.get('tool_name', ''),
        'user_id': tu.get('user_id', None),
        'session_id': tu.get('session_id', None),
        'action': tu.get('action', 'unknown'),
        'created_at': (tu['created_at'].isoformat() + "Z") if isinstance(tu.get('created_at'), datetime) else tu.get('created_at', '')
    }

def log_tool_usage(mongo, tool_name, user_id=None, session_id=None, action=None, details=None):
    """
    Log tool usage to the MongoDB tool_usage collection.
    
    Args:
        mongo: PyMongo instance
        tool_name (str): Name of the tool (e.g., 'financial_health', 'budget')
        user_id (str): ID of the authenticated user (None if unauthenticated)
        session_id (str): Session ID for tracking unauthenticated users
        action (str): Action performed (e.g., 'step1_view', 'dashboard_submit')
        details (dict): Additional details for logging
    """
    session_id = session_id or session.get('sid', str(uuid.uuid4()))  # Generate new session_id if none exists
    try:
        create_tool_usage(mongo, {
            'tool_name': tool_name,
            'user_id': user_id,
            'session_id': session_id,
            'action': action or 'unknown'
        })
        current_app.logger.info(f"Logged tool usage: {tool_name} for session {session_id}", extra={'details': details})
    except Exception as e:
        current_app.logger.error(f"Failed to log tool usage: {str(e)}", extra={'tool_name': tool_name, 'session_id': session_id, 'details': details})
        raise
