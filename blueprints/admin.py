from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from extensions import db
from models import User, ToolUsage, Feedback
from app import admin_required, trans
import logging
import csv
from io import StringIO
from sqlalchemy import func

# Configure logging
logger = logging.getLogger('ficore_app.analytics')

# Define the admin blueprint
admin_bp = Blueprint('admin', __name__, template_folder='templates/admin', url_prefix='/admin')

# Valid tools for filtering
VALID_TOOLS = [
    'register', 'login', 'logout',
    'financial_health', 'budget', 'bill', 'net_worth',
    'emergency_fund', 'learning_hub', 'quiz'
]

@admin_bp.route('/')
@login_required
#@admin_required
def overview():
    """Admin dashboard overview page."""
    lang = session.get('lang', 'en')
    try:
        # User Stats
        total_users = User.query.count()
        last_day = datetime.utcnow() - timedelta(days=1)
        new_users_last_24h = User.query.filter(User.created_at >= last_day).count()

        # Tool Usage
        tool_usage_total = ToolUsage.query.count()
        usage_by_tool = db.session.query(ToolUsage.tool_name, func.count(ToolUsage.id)).group_by(ToolUsage.tool_name).all()
        top_tools = sorted(usage_by_tool, key=lambda x: x[1], reverse=True)[:3]

        # Engagement Metrics
        # Multi-tool users
        multi_tool_users = db.session.query(ToolUsage.user_id, func.count(func.distinct(ToolUsage.tool_name)))\
            .group_by(ToolUsage.user_id)\
            .having(func.count(func.distinct(ToolUsage.tool_name)) > 1)\
            .count()
        total_sessions = db.session.query(func.count(func.distinct(ToolUsage.session_id))).scalar()
        multi_tool_ratio = (multi_tool_users / total_sessions * 100) if total_sessions else 0.0

        # Anonymous to registered conversion
        anon_sessions = db.session.query(ToolUsage.session_id)\
            .filter(ToolUsage.user_id.is_(None), ToolUsage.tool_name.notin_(['register', 'login', 'logout']))\
            .distinct().subquery()
        converted_sessions = db.session.query(ToolUsage.session_id)\
            .filter(ToolUsage.tool_name == 'register', ToolUsage.session_id.in_(anon_sessions))\
            .distinct().count()
        anon_total = db.session.query(anon_sessions).count()
        conversion_rate = (converted_sessions / anon_total * 100) if anon_total else 0.0

        # Feedback
        avg_feedback = db.session.query(func.avg(Feedback.rating)).scalar() or 0.0

        # Data for charts (last 30 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        daily_usage = db.session.query(
            func.date(ToolUsage.created_at).label('date'),
            ToolUsage.tool_name,
            func.count(ToolUsage.id).label('count')
        )\
        .filter(ToolUsage.created_at >= start_date, ToolUsage.created_at <= end_date)\
        .group_by('date', ToolUsage.tool_name)\
        .order_by('date')\
        .all()

        chart_data = {
            'labels': [],
            'registrations': [],
            'logins': [],
            'tool_usage': {tool: [] for tool in VALID_TOOLS if tool not in ['register', 'login', 'logout']}
        }

        current_date = start_date
        while current_date <= end_date:
            chart_data['labels'].append(current_date.strftime('%Y-%m-%d'))
            chart_data['registrations'].append(0)
            chart_data['logins'].append(0)
            for tool in chart_data['tool_usage']:
                chart_data['tool_usage'][tool].append(0)
            current_date += timedelta(days=1)

        for date, tool_name, count in daily_usage:
            idx = (datetime.strptime(date, '%Y-%m-%d') - start_date).days
            if 0 <= idx < len(chart_data['labels']):
                if tool_name == 'register':
                    chart_data['registrations'][idx] = count
                elif tool_name == 'login':
                    chart_data['logins'][idx] = count
                elif tool_name in chart_data['tool_usage']:
                    chart_data['tool_usage'][tool_name][idx] = count

        metrics = {
            'total_users': total_users,
            'new_users_last_24h': new_users_last_24h,
            'tool_usage_total': tool_usage_total,
            'top_tools': top_tools,
            'multi_tool_ratio': round(multi_tool_ratio, 2),
            'conversion_rate': round(conversion_rate, 2),
            'avg_feedback_rating': round(avg_feedback, 2)
        }

        logger.info(f"Admin dashboard overview accessed by {current_user.username}", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template(
            'admin_dashboard.html',
            lang=lang,
            metrics=metrics,
            chart_data=chart_data,
            valid_tools=VALID_TOOLS,
            tool_name=None,
            start_date=None,
            end_date=None
        )
    except Exception as e:
        logger.error(f"Error in admin overview: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans('admin_error', default='An error occurred while loading the dashboard.', lang=lang), 'danger')
        return render_template(
            'admin_dashboard.html',
            lang=lang,
            metrics={},
            chart_data={},
            valid_tools=VALID_TOOLS,
            tool_name=None,
            start_date=None,
            end_date=None
        ), 500

@admin_bp.route('/tool_usage', methods=['GET', 'POST'])
@login_required
#@admin_required
def tool_usage():
    """Detailed tool usage analytics with filters."""
    lang = session.get('lang', 'en')
    try:
        tool_name = request.args.get('tool_name')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        query = ToolUsage.query
        if tool_name and tool_name in VALID_TOOLS:
            query = query.filter_by(tool_name=tool_name)
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(ToolUsage.created_at >= start_date)
        else:
            start_date = None
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(ToolUsage.created_at < end_date)
        else:
            end_date = None

        usage_logs = query.order_by(ToolUsage.created_at.desc()).limit(100).all()

        # Chart data
        chart_data = {
            'labels': [],
            'usage_counts': []
        }
        if start_date and end_date:
            current_date = start_date
            while current_date < end_date:
                chart_data['labels'].append(current_date.strftime('%Y-%m-%d'))
                daily_count = query.filter(
                    func.date(ToolUsage.created_at) == current_date.date()
                ).count()
                chart_data['usage_counts'].append(daily_count)
                current_date += timedelta(days=1)
        else:
            # Default to last 30 days
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
            daily_usage = db.session.query(
                func.date(ToolUsage.created_at).label('date'),
                func.count(ToolUsage.id).label('count')
            )\
            .filter(ToolUsage.created_at >= start_date, ToolUsage.created_at <= end_date)\
            .group_by('date')\
            .order_by('date')\
            .all()
            for date, count in daily_usage:
                chart_data['labels'].append(date)
                chart_data['usage_counts'].append(count)

        logger.info(
            f"Tool usage analytics accessed by {current_user.username}, tool={tool_name}, start={start_date_str}, end={end_date_str}",
            extra={'session_id': session.get('sid', 'no-session-id')}
        )
        return render_template(
            'admin_dashboard.html',
            lang=lang,
            metrics=usage_logs,
            chart_data=chart_data,
            valid_tools=VALID_TOOLS,
            tool_name=tool_name,
            start_date=start_date_str,
            end_date=end_date_str
        )
    except Exception as e:
        logger.error(f"Error in tool usage analytics: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans('admin_error', default='An error occurred while loading analytics.', lang=lang), 'danger')
        return render_template(
            'admin_dashboard.html',
            lang=lang,
            metrics=[],
            chart_data={},
            valid_tools=VALID_TOOLS,
            tool_name=None,
            start_date=None,
            end_date=None
        ), 500

@admin_bp.route('/export_csv', methods=['GET'])
@login_required
#@admin_required
def export_csv():
    """Export filtered tool usage logs as CSV."""
    try:
        tool_name = request.args.get('tool_name')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        query = ToolUsage.query
        if tool_name and tool_name in VALID_TOOLS:
            query = query.filter_by(tool_name=tool_name)
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(ToolUsage.created_at >= start_date)
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(ToolUsage.created_at < end_date)

        usage_logs = query.all()

        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'User ID', 'Session ID', 'Tool Name', 'Created At'])
        for log in usage_logs:
            cw.writerow([
                log.id,
                log.user_id or 'anonymous',
                log.session_id,
                log.tool_name,
                log.created_at.isoformat()
            ])

        output = si.getvalue()
        si.close()

        logger.info(
            f"CSV export generated by {current_user.username}, tool={tool_name}, start={start_date_str}, end={end_date_str}",
            extra={'session_id': session.get('sid', 'no-session-id')}
        )
        return Response(
            output,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=tool_usage_export.csv'}
        )
    except Exception as e:
        logger.error(f"Error in CSV export: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans('admin_export_error', default='An error occurred while exporting CSV.', lang=lang), 'danger')
        return redirect(url_for('admin.tool_usage'))
