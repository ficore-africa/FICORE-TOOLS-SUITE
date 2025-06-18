from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, Response
from flask_login import current_user
from datetime import datetime, timedelta
from app import admin_required, trans, logger as app_logger, custom_login_required
from models import get_user, get_tool_usage, get_feedback, to_dict_tool_usage, to_dict_feedback
import logging
import csv
from io import StringIO
from extensions import mongo  # Import mongo from extensions

# Configure logging with SessionAdapter
logger = logging.getLogger('ficore_app.admin')  # Namespaced logger

# Define the admin blueprint
admin_bp = Blueprint('admin', __name__, template_folder='templates/admin', url_prefix='/admin')

# Valid tools for filtering
VALID_TOOLS = [
    'register', 'login', 'logout',
    'financial_health', 'budget', 'bill', 'net_worth',
    'emergency_fund', 'learning_hub', 'quiz'
]

@admin_bp.route('/')
@custom_login_required
@admin_required
def overview():
    """Admin dashboard overview page."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    session_id = session.get('sid', 'no-session-id')
    try:
        # Use mongo.db directly without reassignment
        db = mongo.db

        # User Stats
        total_users = db.users.count_documents({})
        last_day = datetime.utcnow() - timedelta(days=1)
        new_users_last_24h = db.users.count_documents({'created_at': {'$gte': last_day}})

        # Referral Stats
        total_referrals = db.users.count_documents({'referred_by_id': {'$ne': None}})
        new_referrals_last_24h = db.users.count_documents({
            'referred_by_id': {'$ne': None},
            'created_at': {'$gte': last_day}
        })
        referral_conversion_rate = (total_referrals / total_users * 100) if total_users else 0.0

        # Tool Usage Stats
        tool_usage_total = db.tool_usage.count_documents({})
        usage_by_tool = list(db.tool_usage.aggregate([
            {'$group': {'_id': '$tool_name', 'count': {'$sum': 1}}},
            {'$project': {'tool_name': '$_id', 'count': 1, '_id': 0}}
        ]))
        top_tools = sorted(usage_by_tool, key=lambda x: x['count'], reverse=True)[:3]

        # Action Breakdown for Top Tools
        action_breakdown = {}
        for tool in [t['tool_name'] for t in top_tools]:
            actions = list(db.tool_usage.aggregate([
                {'$match': {'tool_name': tool}},
                {'$group': {'_id': '$action', 'count': {'$sum': 1}}},
                {'$project': {'action': '$_id', 'count': 1, '_id': 0}},
                {'$sort': {'count': -1}},
                {'$limit': 5}
            ]))
            action_breakdown[tool] = [(a['action'], a['count']) for a in actions] if actions else []

        # Feedback
        avg_feedback = list(db.feedback.aggregate([
            {'$group': {'_id': None, 'avg_rating': {'$avg': '$rating'}}},
            {'$project': {'avg_rating': 1, '_id': 0}}
        ]))
        avg_feedback = avg_feedback[0]['avg_rating'] if avg_feedback else 0.0

        metrics = {
            'total_users': total_users,
            'new_users_last_24h': new_users_last_24h,
            'total_referrals': total_referrals,
            'new_referrals_last_24h': new_referrals_last_24h,
            'referral_conversion_rate': round(referral_conversion_rate, 2),
            'tool_usage_total': tool_usage_total,
            'top_tools': [(t['tool_name'], t['count']) for t in top_tools],
            'action_breakdown': action_breakdown,
            'avg_feedback_rating': round(avg_feedback, 2)
        }

        # Log metrics for debugging
        logger.debug(f"Metrics prepared: {metrics}", extra={'session_id': session_id})

        logger.info(f"Admin dashboard overview accessed by {current_user.username if current_user.is_authenticated else 'anonymous'}", extra={'session_id': session_id})
        return render_template(
            'admin_dashboard.html',
            lang=lang,
            metrics=metrics,
            valid_tools=VALID_TOOLS[3:],
            tool_name=None,
            start_date=None,
            end_date=None
        )
    except Exception as e:
        logger.error(f"Error in admin overview: {str(e)}", extra={'session_id': session_id})
        flash(trans('admin_error', default='An error occurred while loading the dashboard.', lang=lang), 'danger')
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@admin_bp.route('/tool_usage', methods=['GET', 'POST'])
@custom_login_required
@admin_required
def tool_usage():
    """Detailed tool usage analytics with filters."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    session_id = session.get('sid', 'no-session-id')
    try:
        db = mongo.db
        tool_name = request.args.get('tool_name')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        action = request.args.get('action')

        filters = {}
        if tool_name and tool_name in VALID_TOOLS[3:]:
            filters['tool_name'] = tool_name
        if action:
            filters['action'] = action
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            filters['created_at'] = filters.get('created_at', {})
            filters['created_at']['$gte'] = start_date
        else:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            filters['created_at'] = filters.get('created_at', {})
            filters['created_at']['$lt'] = end_date
        else:
            end_date = datetime.utcnow()

        usage_logs = list(db.tool_usage.find(filters, {'_id': False}).sort('created_at', -1).limit(100))
        usage_logs = [to_dict_tool_usage(log) for log in usage_logs]

        # Available actions for the selected tool
        available_actions = db.tool_usage.distinct('action', {'tool_name': tool_name} if tool_name else {})
        available_actions = [a for a in available_actions if a]

        logger.info(f"Tool usage analytics accessed by {current_user.username if current_user.is_authenticated else 'anonymous'}, tool={tool_name}, action={action}, start={start_date_str}, end={end_date_str}", extra={'session_id': session_id})
        return render_template(
            'admin_dashboard.html',
            lang=lang,
            metrics=usage_logs,
            valid_tools=VALID_TOOLS[3:],
            tool_name=tool_name,
            start_date=start_date_str,
            end_date=end_date_str,
            action=action,
            available_actions=available_actions
        )
    except Exception as e:
        logger.error(f"Error in tool usage analytics: {str(e)}", extra={'session_id': session_id})
        flash(trans('admin_error', default='Error loading analytics.', lang=lang), 'error')
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@admin_bp.route('/export_csv', methods=['GET'])
@custom_login_required
@admin_required
def export_csv():
    """Export filtered tool usage logs as CSV."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        session.modified = True
    lang = session.get('lang', 'en')
    session_id = session.get('sid', 'no-session-id')
    try:
        db = mongo.db
        tool_name = request.args.get('tool_name')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        action = request.args.get('action')

        filters = {}
        if tool_name and tool_name in VALID_TOOLS[3:]:
            filters['tool_name'] = tool_name
        if action:
            filters['action'] = action
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            filters['created_at'] = filters.get('created_at', {})
            filters['created_at']['$gte'] = start_date
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            filters['created_at'] = filters.get('created_at', {})
            filters['created_at']['$lt'] = end_date

        usage_logs = list(db.tool_usage.find(filters, {'_id': False}))
        usage_logs = [to_dict_tool_usage(log) for log in usage_logs]

        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'User ID', 'Session ID', 'Tool Name', 'Action', 'Created At'])
        for log in usage_logs:
            cw.writerow([
                log['id'],
                log['user_id'] or 'anonymous',
                log['session_id'],
                log['tool_name'],
                log['action'] or 'N/A',
                log['created_at'] or 'N/A'
            ])

        output = si.getvalue()
        si.close()

        logger.info(f"CSV export generated by {current_user.username if current_user.is_authenticated else 'anonymous'}, tool={tool_name}, action={action}, start={start_date_str}, end={end_date_str}", extra={'session_id': session_id})
        return Response(
            output,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=tool_usage_export.csv'}
        )
    except Exception as e:
        logger.error(f"Error in CSV export: {str(e)}", extra={'session_id': session_id})
        flash(trans('admin_export_error', default='Error exporting CSV.', lang=lang), 'error')
        return redirect(url_for('index'))
