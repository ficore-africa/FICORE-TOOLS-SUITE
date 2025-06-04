"""Initial schema with all models including updated QuizResult, NetWorth, and LearningProgress

Revision ID: initial_schema
Revises: 
Create Date: 2025-06-03 22:44:00
"""

from alembic import op
import sqlalchemy as sa

revision = 'initial_schema'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )

    # Courses table
    op.create_table(
        'courses',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('title_key', sa.String(length=100), nullable=False),
        sa.Column('title_en', sa.String(length=100), nullable=False),
        sa.Column('title_ha', sa.String(length=100), nullable=False),
        sa.Column('description_en', sa.Text(), nullable=False),
        sa.Column('description_ha', sa.Text(), nullable=False),
        sa.Column('is_premium', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # FinancialHealth table
    op.create_table(
        'financial_health',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('first_name', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('user_type', sa.String(length=20), nullable=True),
        sa.Column('send_email', sa.Boolean(), nullable=False),
        sa.Column('income', sa.Float(), nullable=True),
        sa.Column('expenses', sa.Float(), nullable=True),
        sa.Column('debt', sa.Float(), nullable=True),
        sa.Column('interest_rate', sa.Float(), nullable=True),
        sa.Column('debt_to_income', sa.Float(), nullable=True),
        sa.Column('savings_rate', sa.Float(), nullable=True),
        sa.Column('interest_burden', sa.Float(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('status_key', sa.String(length=50), nullable=True),
        sa.Column('badges', sa.Text(), nullable=True),
        sa.Column('step', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_financial_health_session_id', 'financial_health', ['session_id'], unique=False)
    op.create_index('ix_financial_health_user_id', 'financial_health', ['user_id'], unique=False)

    # Budget table
    op.create_table(
        'budget',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('user_email', sa.String(length=120), nullable=True),
        sa.Column('income', sa.Float(), nullable=False),
        sa.Column('fixed_expenses', sa.Float(), nullable=False),
        sa.Column('variable_expenses', sa.Float(), nullable=False),
        sa.Column('savings_goal', sa.Float(), nullable=False),
        sa.Column('surplus_deficit', sa.Float(), nullable=True),
        sa.Column('housing', sa.Float(), nullable=False),
        sa.Column('food', sa.Float(), nullable=False),
        sa.Column('transport', sa.Float(), nullable=False),
        sa.Column('dependents', sa.Float(), nullable=False),
        sa.Column('miscellaneous', sa.Float(), nullable=False),
        sa.Column('others', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_budget_session_id', 'budget', ['session_id'], unique=False)
    op.create_index('ix_budget_user_id', 'budget', ['user_id'], unique=False)

    # Bills table
    op.create_table(
        'bills',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('user_email', sa.String(length=120), nullable=True),
        sa.Column('first_name', sa.String(length=50), nullable=True),
        sa.Column('bill_name', sa.String(length=100), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('frequency', sa.String(length=20), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('send_email', sa.Boolean(), nullable=False),
        sa.Column('reminder_days', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bills_session_id', 'bills', ['session_id'], unique=False)
    op.create_index('ix_bills_user_id', 'bills', ['user_id'], unique=False)

    # NetWorth table
    op.create_table(
        'net_worth',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('first_name', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('send_email', sa.Boolean(), nullable=False),
        sa.Column('cash_savings', sa.Float(), nullable=True),
        sa.Column('investments', sa.Float(), nullable=True),
        sa.Column('property', sa.Float(), nullable=True),
        sa.Column('loans', sa.Float(), nullable=True),
        sa.Column('total_assets', sa.Float(), nullable=True),
        sa.Column('total_liabilities', sa.Float(), nullable=True),
        sa.Column('net_worth', sa.Float(), nullable=True),
        sa.Column('badges', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_net_worth_session_id', 'net_worth', ['session_id'], unique=False)
    op.create_index('ix_net_worth_user_id', 'net_worth', ['user_id'], unique=False)

    # EmergencyFund table
    op.create_table(
        'emergency_fund',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('first_name', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('email_opt_in', sa.Boolean(), nullable=False),
        sa.Column('lang', sa.String(length=10), nullable=True),
        sa.Column('monthly_expenses', sa.Float(), nullable=True),
        sa.Column('monthly_income', sa.Float(), nullable=True),
        sa.Column('current_savings', sa.Float(), nullable=True),
        sa.Column('risk_tolerance_level', sa.String(length=20), nullable=True),
        sa.Column('dependents', sa.Integer(), nullable=True),
        sa.Column('timeline', sa.Integer(), nullable=True),
        sa.Column('recommended_months', sa.Integer(), nullable=True),
        sa.Column('target_amount', sa.Float(), nullable=True),
        sa.Column('savings_gap', sa.Float(), nullable=True),
        sa.Column('monthly_savings', sa.Float(), nullable=True),
        sa.Column('percent_of_income', sa.Float(), nullable=True),
        sa.Column('badges', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_emergency_fund_session_id', 'emergency_fund', ['session_id'], unique=False)
    op.create_index('ix_emergency_fund_user_id', 'emergency_fund', ['user_id'], unique=False)

    # LearningProgress table
    op.create_table(
        'learning_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('course_id', sa.String(length=50), nullable=False),
        sa.Column('lessons_completed', sa.Text(), nullable=False),
        sa.Column('quiz_scores', sa.Text(), nullable=False),
        sa.Column('current_lesson', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'course_id', name='uix_user_course_id'),
        sa.UniqueConstraint('session_id', 'course_id', name='uix_session_course_id')
    )
    op.create_index('ix_learning_progress_session_id', 'learning_progress', ['session_id'], unique=False)
    op.create_index('ix_learning_progress_user_id', 'learning_progress', ['user_id'], unique=False)

    # QuizResults table
    op.create_table(
        'quiz_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('first_name', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('send_email', sa.Boolean(), nullable=False),
        sa.Column('personality', sa.String(length=50), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('badges', sa.Text(), nullable=True),
        sa.Column('insights', sa.Text(), nullable=True),
        sa.Column('tips', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_quiz_results_session_id', 'quiz_results', ['session_id'], unique=False)
    op.create_index('ix_quiz_results_user_id', 'quiz_results', ['user_id'], unique=False)

def downgrade():
    op.drop_index('ix_quiz_results_user_id', table_name='quiz_results')
    op.drop_index('ix_quiz_results_session_id', table_name='quiz_results')
    op.drop_table('quiz_results')
    op.drop_index('ix_learning_progress_user_id', table_name='learning_progress')
    op.drop_index('ix_learning_progress_session_id', table_name='learning_progress')
    op.drop_table('learning_progress')
    op.drop_index('ix_emergency_fund_user_id', table_name='emergency_fund')
    op.drop_index('ix_emergency_fund_session_id', table_name='emergency_fund')
    op.drop_table('emergency_fund')
    op.drop_index('ix_net_worth_user_id', table_name='net_worth')
    op.drop_index('ix_net_worth_session_id', table_name='net_worth')
    op.drop_table('net_worth')
    op.drop_index('ix_bills_user_id', table_name='bills')
    op.drop_index('ix_bills_session_id', table_name='bills')
    op.drop_table('bills')
    op.drop_index('ix_budget_user_id', table_name='budget')
    op.drop_index('ix_budget_session_id', table_name='budget')
    op.drop_table('budget')
    op.drop_index('ix_financial_health_user_id', table_name='financial_health')
    op.drop_index('ix_financial_health_session_id', table_name='financial_health')
    op.drop_table('financial_health')
    op.drop_table('courses')
    op.drop_table('users')
