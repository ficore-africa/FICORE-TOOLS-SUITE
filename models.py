from extensions import db
import json
from datetime import datetime, date
from flask_login import UserMixin  # Add UserMixin import


class User(db.Model, UserMixin):  # Add UserMixin
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    lang = db.Column(db.String(10), default='en')

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.String(50), primary_key=True)
    title_key = db.Column(db.String(100), nullable=False)
    title_en = db.Column(db.String(100), nullable=False)
    title_ha = db.Column(db.String(100), nullable=False)
    description_en = db.Column(db.Text, nullable=False)
    description_ha = db.Column(db.Text, nullable=False)
    is_premium = db.Column(db.Boolean, default=False, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title_key': self.title_key,
            'title_en': self.title_en,
            'title_ha': self.title_ha,
            'description_en': self.description_en,
            'description_ha': self.description_ha,
            'is_premium': self.is_premium
        }

class FinancialHealth(db.Model):
    __tablename__ = 'financial_health'
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_id = db.Column(db.String(36), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    first_name = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    user_type = db.Column(db.String(20), nullable=True)
    send_email = db.Column(db.Boolean, default=False, nullable=False)
    income = db.Column(db.Float, nullable=True)
    expenses = db.Column(db.Float, nullable=True)
    debt = db.Column(db.Float, nullable=True)
    interest_rate = db.Column(db.Float, nullable=True)
    debt_to_income = db.Column(db.Float, nullable=True)
    savings_rate = db.Column(db.Float, nullable=True)
    interest_burden = db.Column(db.Float, nullable=True)
    score = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(50), nullable=True)
    status_key = db.Column(db.String(50), nullable=True)
    badges = db.Column(db.Text, nullable=True)  # JSON string
    step = db.Column(db.Integer, nullable=True)
    user = db.relationship('User', backref='financial_health_records')

    __table_args__ = (
        db.Index('ix_financial_health_session_id', 'session_id'),
        db.Index('ix_financial_health_user_id', 'user_id')
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat() + "Z",
            'first_name': self.first_name,
            'email': self.email,
            'user_type': self.user_type,
            'send_email': self.send_email,
            'income': self.income,
            'expenses': self.expenses,
            'debt': self.debt,
            'interest_rate': self.interest_rate,
            'debt_to_income': self.debt_to_income,
            'savings_rate': self.savings_rate,
            'interest_burden': self.interest_burden,
            'score': self.score,
            'status': self.status,
            'status_key': self.status_key,
            'badges': json.loads(self.badges) if self.badges else [],
            'step': self.step
        }

class Budget(db.Model):
    __tablename__ = 'budget'
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_id = db.Column(db.String(36), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_email = db.Column(db.String(120), nullable=True)
    income = db.Column(db.Float, nullable=False, default=0.0)
    fixed_expenses = db.Column(db.Float, nullable=False, default=0.0)
    variable_expenses = db.Column(db.Float, nullable=False, default=0.0)
    savings_goal = db.Column(db.Float, nullable=False, default=0.0)
    surplus_deficit = db.Column(db.Float, nullable=True)
    housing = db.Column(db.Float, nullable=False, default=0.0)
    food = db.Column(db.Float, nullable=False, default=0.0)
    transport = db.Column(db.Float, nullable=False, default=0.0)
    dependents = db.Column(db.Float, nullable=False, default=0.0)
    miscellaneous = db.Column(db.Float, nullable=False, default=0.0)
    others = db.Column(db.Float, nullable=False, default=0.0)
    user = db.relationship('User', backref='budgets')

    __table_args__ = (
        db.Index('ix_budget_session_id', 'session_id'),
        db.Index('ix_budget_user_id', 'user_id')
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat() + "Z",
            'user_email': self.user_email,
            'income': self.income,
            'fixed_expenses': self.fixed_expenses,
            'variable_expenses': self.variable_expenses,
            'savings_goal': self.savings_goal,
            'surplus_deficit': self.surplus_deficit,
            'housing': self.housing,
            'food': self.food,
            'transport': self.transport,
            'dependents': self.dependents,
            'miscellaneous': self.miscellaneous,
            'others': self.others
        }

class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_id = db.Column(db.String(36), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_email = db.Column(db.String(120), nullable=True)
    first_name = db.Column(db.String(50), nullable=True)
    bill_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    frequency = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    send_email = db.Column(db.Boolean, nullable=False, default=False)
    reminder_days = db.Column(db.Integer, nullable=True)
    user = db.relationship('User', backref='bills')

    __table_args__ = (
        db.Index('ix_bills_session_id', 'session_id'),
        db.Index('ix_bills_user_id', 'user_id')
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat() + "Z",
            'user_email': self.user_email,
            'first_name': self.first_name,
            'bill_name': self.bill_name,
            'amount': self.amount,
            'due_date': self.due_date.strftime('%Y-%m-%d') if self.due_date else None,
            'frequency': self.frequency,
            'category': self.category,
            'status': self.status,
            'send_email': self.send_email,
            'reminder_days': self.reminder_days
        }

class NetWorth(db.Model):
    __tablename__ = 'net_worth'
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_id = db.Column(db.String(36), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    first_name = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    send_email = db.Column(db.Boolean, default=False, nullable=False)
    cash_savings = db.Column(db.Float, nullable=True)
    investments = db.Column(db.Float, nullable=True)
    property = db.Column(db.Float, nullable=True)
    loans = db.Column(db.Float, nullable=True)
    total_assets = db.Column(db.Float, nullable=True)
    total_liabilities = db.Column(db.Float, nullable=True)
    net_worth = db.Column(db.Float, nullable=True)
    badges = db.Column(db.Text, nullable=True)  # JSON string
    user = db.relationship('User', backref='net_worth_records')

    __table_args__ = (
        db.Index('ix_net_worth_session_id', 'session_id'),
        db.Index('ix_net_worth_user_id', 'user_id')
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat() + "Z",
            'first_name': self.first_name,
            'email': self.email,
            'send_email': self.send_email,
            'cash_savings': self.cash_savings,
            'investments': self.investments,
            'property': self.property,
            'loans': self.loans,
            'total_assets': self.total_assets,
            'total_liabilities': self.total_liabilities,
            'net_worth': self.net_worth,
            'badges': json.loads(self.badges) if self.badges else []
        }

class EmergencyFund(db.Model):
    __tablename__ = 'emergency_fund'
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_id = db.Column(db.String(36), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    first_name = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    email_opt_in = db.Column(db.Boolean, default=False, nullable=False)
    lang = db.Column(db.String(10), nullable=True)
    monthly_expenses = db.Column(db.Float, nullable=True)
    monthly_income = db.Column(db.Float, nullable=True)
    current_savings = db.Column(db.Float, nullable=True)
    risk_tolerance_level = db.Column(db.String(20), nullable=True)
    dependents = db.Column(db.Integer, nullable=True)
    timeline = db.Column(db.Integer, nullable=True)
    recommended_months = db.Column(db.Integer, nullable=True)
    target_amount = db.Column(db.Float, nullable=True)
    savings_gap = db.Column(db.Float, nullable=True)
    monthly_savings = db.Column(db.Float, nullable=True)
    percent_of_income = db.Column(db.Float, nullable=True)
    badges = db.Column(db.Text, nullable=True)  # JSON string
    user = db.relationship('User', backref='emergency_funds')

    __table_args__ = (
        db.Index('ix_emergency_fund_session_id', 'session_id'),
        db.Index('ix_emergency_fund_user_id', 'user_id')
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat() + "Z",
            'first_name': self.first_name,
            'email': self.email,
            'email_opt_in': self.email_opt_in,
            'lang': self.lang,
            'monthly_expenses': self.monthly_expenses,
            'monthly_income': self.monthly_income,
            'current_savings': self.current_savings,
            'risk_tolerance_level': self.risk_tolerance_level,
            'dependents': self.dependents,
            'timeline': self.timeline,
            'recommended_months': self.recommended_months,
            'target_amount': self.target_amount,
            'savings_gap': self.savings_gap,
            'monthly_savings': self.monthly_savings,
            'percent_of_income': self.percent_of_income,
            'badges': json.loads(self.badges) if self.badges else []
        }

class LearningProgress(db.Model):
    __tablename__ = 'learning_progress'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_id = db.Column(db.String(36), nullable=False)
    course_id = db.Column(db.String(50), nullable=False)
    lessons_completed = db.Column(db.Text, default='[]', nullable=False)  # JSON string
    quiz_scores = db.Column(db.Text, default='{}', nullable=False)  # JSON string
    current_lesson = db.Column(db.String(50), nullable=True)
    user = db.relationship('User', backref='learning_progress_records')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'course_id', name='uix_user_course_id'),
        db.UniqueConstraint('session_id', 'course_id', name='uix_session_course_id'),
        db.Index('ix_learning_progress_session_id', 'session_id'),
        db.Index('ix_learning_progress_user_id', 'user_id')
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'course_id': self.course_id,
            'lessons_completed': json.loads(self.lessons_completed),
            'quiz_scores': json.loads(self.quiz_scores),
            'current_lesson': self.current_lesson
        }

class QuizResult(db.Model):
    __tablename__ = 'quiz_results'
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_id = db.Column(db.String(36), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    first_name = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    send_email = db.Column(db.Boolean, default=False, nullable=False)
    personality = db.Column(db.String(50), nullable=True)
    score = db.Column(db.Integer, nullable=True)
    badges = db.Column(db.Text, nullable=True)  # JSON string
    insights = db.Column(db.Text, nullable=True)  # JSON string
    tips = db.Column(db.Text, nullable=True)  # JSON string
    user = db.relationship('User', backref='quiz_results')

    __table_args__ = (
        db.Index('ix_quiz_results_session_id', 'session_id'),
        db.Index('ix_quiz_results_user_id', 'user_id')
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat() + "Z",
            'first_name': self.first_name,
            'email': self.email,
            'send_email': self.send_email,
            'personality': self.personality,
            'score': self.score,
            'badges': json.loads(self.badges) if self.badges else [],
            'insights': json.loads(self.insights) if self.insights else [],
            'tips': json.loads(self.tips) if self.tips else []
        }
