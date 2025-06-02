from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email, ValidationError
from json_store import JsonStorage
from mailersend_email import send_email, EMAIL_CONFIG  # Modified to include EMAIL_CONFIG
from datetime import datetime
import uuid

try:
    from app import trans
except ImportError:
    def trans(key, lang=None):
        return key

def init_storage(app):
    """Initialize storage with app context."""
    with app.app_context():
        storage_managers = {
            'financial_health': JsonStorage('data/financial_health.json', logger_instance=app.logger),
            'progress': JsonStorage('data/user_progress.json', logger_instance=app.logger)
        }
        # Verify file accessibility
        for name, storage in storage_managers.items():
            try:
                storage._read()  # Test file access
                app.logger.info(f"Successfully verified access to {name} storage at {storage.filename}")
            except Exception as e:
                app.logger.error(f"Failed to access {name} storage at {storage.filename}: {str(e)}")
                raise RuntimeError(f"Cannot initialize {name} storage: {str(e)}")
        return storage_managers

financial_health_bp = Blueprint('financial_health', __name__, url_prefix='/financial_health')

class Step1Form(FlaskForm):
    first_name = StringField()
    email = StringField()
    user_type = SelectField()
    send_email = BooleanField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        # Set labels dynamically
        self.first_name.label.text = trans('financial_health_first_name', lang=lang)
        self.email.label.text = trans('financial_health_email', lang=lang)
        self.user_type.label.text = trans('financial_health_user_type', lang=lang)
        self.send_email.label.text = trans('financial_health_send_email', lang=lang)
        self.submit.label.text = trans('financial_health_next', lang=lang)
        # Set validators dynamically
        self.first_name.validators = [DataRequired(message=trans('financial_health_first_name_required', lang=lang))]
        self.email.validators = [Optional(), Email(message=trans('financial_health_email_invalid', lang=lang))]
        # Set choices dynamically
        self.user_type.choices = [
            ('individual', trans('financial_health_user_type_individual', lang=lang)),
            ('business', trans('financial_health_user_type_business', lang=lang))
        ]

class Step2Form(FlaskForm):
    income = FloatField()
    expenses = FloatField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        # Set labels dynamically
        self.income.label.text = trans('financial_health_monthly_income', lang=lang)
        self.expenses.label.text = trans('financial_health_monthly_expenses', lang=lang)
        self.submit.label.text = trans('financial_health_next', lang=lang)
        # Set validators dynamically
        self.income.validators = [
            DataRequired(message=trans('financial_health_income_required', lang=lang)),
            NumberRange(min=0, max=10000000000, message=trans('financial_health_income_max', lang=lang))
        ]
        self.expenses.validators = [
            DataRequired(message=trans('financial_health_expenses_required', lang=lang)),
            NumberRange(min=0, max=10000000000, message=trans('financial_health_expenses_max', lang=lang))
        ]

    def validate_income(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data)
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid income input: {field.data}")
                raise ValidationError(trans('financial_health_income_invalid', lang=session.get('lang', 'en')))

    def validate_expenses(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data)
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid expenses input: {field.data}")
                raise ValidationError(trans('financial_health_expenses_invalid', lang=session.get('lang', 'en')))

class Step3Form(FlaskForm):
    debt = FloatField()
    interest_rate = FloatField()
    submit = SubmitField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')
        # Set labels dynamically
        self.debt.label.text = trans('financial_health_total_debt', lang=lang)
        self.interest_rate.label.text = trans('financial_health_average_interest_rate', lang=lang)
        self.submit.label.text = trans('financial_health_submit', lang=lang)
        # Set validators dynamically
        self.debt.validators = [
            Optional(),
            NumberRange(min=0, max=10000000000, message=trans('financial_health_debt_max', lang=lang))
        ]
        self.interest_rate.validators = [
            Optional(),
            NumberRange(min=0, message=trans('financial_health_interest_rate_positive', lang=lang))
        ]

    def validate_debt(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data) if cleaned_data else None
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid debt input: {field.data}")
                raise ValidationError(trans('financial_health_debt_invalid', lang=session.get('lang', 'en')))

    def validate_interest_rate(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data) if cleaned_data else None
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid interest rate input: {field.data}")
                raise ValidationError(trans('financial_health_interest_rate_invalid', lang=session.get('lang', 'en')))

@financial_health_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle financial health step 1 form (personal info)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step1Form()
    current_app.logger.info(f"Starting step1 for session {session['sid']}")
    try:
        if request.method == 'POST':
            current_app.logger.debug(f"Received POST data: {request.form}")
            if not form.validate_on_submit():
                current_app.logger.warning(f"Form validation failed: {form.errors}")
                flash(trans("financial_health_form_errors", lang=lang), "danger")
                return render_template('health_score_step1.html', form=form, trans=trans, lang=lang)
            
            form_data = form.data.copy()
            if form_data.get('email') and not isinstance(form_data['email'], str):
                current_app.logger.error(f"Invalid email type: {type(form_data['email'])}")
                raise ValueError(trans("financial_health_email_must_be_string", lang=lang))
            session['health_step1'] = form_data
            current_app.logger.debug(f"Validated form data: {form_data}")

            try:
                financial_health_storage = current_app.config['STORAGE_MANAGERS']['financial_health']
                storage_data = {
                    'step': 1,
                    'data': form_data
                }
                record_id = financial_health_storage.append(storage_data, user_email=form_data.get('email'), session_id=session['sid'])
                if record_id:
                    current_app.logger.info(f"Step1 form data appended to storage with record ID {record_id} for session {session['sid']}")
                else:
                    current_app.logger.error("Failed to append Step1 data to storage")
                    flash(trans("financial_health_save_data_error", lang=lang), "danger")
                    return render_template('health_score_step1.html', form=form, trans=trans, lang=lang), 500
            except Exception as storage_error:
                current_app.logger.exception(f"Failed to append to JSON storage: {str(storage_error)}")
                flash(trans("financial_health_save_data_error", lang=lang), "danger")
                return render_template('health_score_step1.html', form=form, trans=trans, lang=lang), 500

            current_app.logger.debug(f"Step1 form data saved to session: {form_data}")
            return redirect(url_for('financial_health.step2'))
        return render_template('health_score_step1.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step1: {str(e)}")
        flash(trans("financial_health_error_personal_info", lang=lang), "danger")
        return render_template('health_score_step1.html', form=form, trans=trans, lang=lang), 500

@financial_health_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle financial health step 2 form (income and expenses)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step2Form()
    current_app.logger.info(f"Starting step2 for session {session['sid']}")
    try:
        if request.method == 'POST':
            if not form.validate_on_submit():
                current_app.logger.warning(f"Form validation failed: {form.errors}")
                flash(trans("financial_health_form_errors", lang=lang), "danger")
                return render_template('health_score_step2.html', form=form, trans=trans, lang=lang)
            session['health_step2'] = {
                'income': float(form.income.data),
                'expenses': float(form.expenses.data),
                'submit': form.submit.data
            }
            try:
                financial_health_storage = current_app.config['STORAGE_MANAGERS']['financial_health']
                storage_data = {
                    'step': 2,
                    'data': session['health_step2']
                }
                record_id = financial_health_storage.append(storage_data, session_id=session['sid'])
                if record_id:
                    current_app.logger.info(f"Step2 form data appended to storage with record ID {record_id} for session {session['sid']}")
                else:
                    current_app.logger.error("Failed to append Step2 data to storage")
                    flash(trans("financial_health_save_data_error", lang=lang), "danger")
                    return render_template('health_score_step2.html', form=form, trans=trans, lang=lang), 500
            except Exception as storage_error:
                current_app.logger.exception(f"Failed to append to JSON storage: {str(storage_error)}")
                flash(trans("financial_health_save_data_error", lang=lang), "danger")
                return render_template('health_score_step2.html', form=form, trans=trans, lang=lang), 500

            current_app.logger.debug(f"Step2 form data saved to session: {session['health_step2']}")
            return redirect(url_for('financial_health.step3'))
        return render_template('health_score_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step2: {str(e)}")
        flash(trans("financial_health_error_income_expenses", lang=lang), "danger")
        return render_template('health_score_step2.html', form=form, trans=trans, lang=lang), 500

@financial_health_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    """Handle financial health step 3 form (debt and interest) and calculate score."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step3Form()
    current_app.logger.info(f"Starting step3 for session {session['sid']}")
    try:
        if request.method == 'POST':
            if not form.validate_on_submit():
                current_app.logger.warning(f"Form validation failed: {form.errors}")
                flash(trans("financial_health_form_errors", lang=lang), "danger")
                return render_template('health_score_step3.html', form=form, trans=trans, lang=lang)

            data = {
                'debt': float(form.debt.data) if form.debt.data is not None else 0,
                'interest_rate': float(form.interest_rate.data) if form.interest_rate.data is not None else 0,
                'submit': form.submit.data
            }
            step1_data = session.get('health_step1', {})
            step2_data = session.get('health_step2', {})
            current_app.logger.debug(f"Step1 data: {step1_data}")
            current_app.logger.debug(f"Step2 data: {step2_data}")
            current_app.logger.debug(f"Step3 form data: {data}")

            income = float(step2_data.get('income', 0) or 0)
            expenses = float(step2_data.get('expenses', 0) or 0)
            debt = data.get('debt', 0)
            interest_rate = data.get('interest_rate', 0)

            if income <= 0:
                current_app.logger.error("Income is zero or negative, cannot calculate financial health metrics")
                flash(trans("financial_health_income_zero_error", lang=lang), "danger")
                return render_template('health_score_step3.html', form=form, trans=trans, lang=lang), 500

            current_app.logger.info("Calculating financial health metrics")
            try:
                debt_to_income = (debt / income * 100)
                savings_rate = ((income - expenses) / income * 100)
                interest_burden = (interest_rate * debt / 100) if debt > 0 else 0
            except ZeroDivisionError as zde:
                current_app.logger.error(f"ZeroDivisionError during metric calculation: {str(zde)}")
                flash(trans("financial_health_calculation_error", lang=lang), "danger")
                return render_template('health_score_step3.html', form=form, trans=trans, lang=lang), 500

            score = 100
            if debt_to_income > 0:
                score -= min(debt_to_income, 50)
            if savings_rate < 0:
                score -= min(abs(savings_rate), 30)
            elif savings_rate > 0:
                score += min(savings_rate / 2, 20)
            score -= min(interest_burden, 20)
            score = max(0, min(100, round(score)))
            current_app.logger.debug(f"Calculated score: {score}")

            status = (trans("financial_health_status_excellent", lang=lang) if score >= 80 else
                      trans("financial_health_status_good", lang=lang) if score >= 60 else
                      trans("financial_health_status_needs_improvement", lang=lang))
            badges = []
            if score >= 80:
                badges.append(trans("financial_health_badge_financial_star", lang=lang))
            if debt_to_income < 20:
                badges.append(trans("financial_health_badge_debt_manager", lang=lang))
            if savings_rate >= 20:
                badges.append(trans("financial_health_badge_savings_pro", lang=lang))
            if interest_burden == 0 and debt > 0:
                badges.append(trans("financial_health_badge_interest_free", lang=lang))
            current_app.logger.debug(f"Status: {status}, Badges: {badges}")

            record = {
                "first_name": step1_data.get('first_name', ''),
                "email": step1_data.get('email', ''),
                "user_type": step1_data.get('user_type', 'individual'),
                "income": income,
                "expenses": expenses,
                "debt": debt,
                "interest_rate": interest_rate,
                "debt_to_income": debt_to_income,
                "savings_rate": savings_rate,
                "interest_burden": interest_burden,
                "score": score,
                "status": status,
                "status_key": status_key,
                "badges": badges,
                "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            session['health_record'] = record
            try:
                financial_health_storage = current_app.config['STORAGE_MANAGERS']['financial_health']
                storage_data = {
                    'step': 3,
                    'data': record
                }
                record_id = financial_health_storage.append(storage_data, user_email=step1_data.get('email'), session_id=session['sid'])
                if record_id:
                    current_app.logger.info(f"Step3 final record appended to storage with record ID {record_id} for session {session['sid']}")
                else:
                    current_app.logger.error("Failed to append Step3 final record to storage")
                    flash(trans("financial_health_save_final_error", lang=lang), "danger")
                    return render_template('health_score_step3.html', form=form, trans=trans, lang=lang), 500
            except Exception as storage_error:
                current_app.logger.exception(f"Failed to append to JSON storage: {str(storage_error)}")
                flash(trans("financial_health_save_final_error", lang=lang), "danger")
                return render_template('health_score_step3.html', form=form, trans=trans, lang=lang), 500

            current_app.logger.debug(f"Session contents after save: {dict(session)}")

            email = step1_data.get('email')
            send_email_flag = step1_data.get('send_email', False)
            if send_email_flag and email:
                current_app.logger.info(f"Sending email to {email}")
                try:
                    config = EMAIL_CONFIG["financial_health"]
                    subject = trans(config["subject_key"], lang=lang)
                    template = config["template"]
                    send_email(
                        app=current_app,
                        logger=current_app.logger,
                        to_email=email,
                        subject=subject,
                        template_name=template,
                        data={
                            "first_name": record["first_name"],
                            "score": record["score"],
                            "status": record["status"],
                            "income": record["income"],
                            "expenses": record["expenses"],
                            "debt": record["debt"],
                            "interest_rate": record["interest_rate"],
                            "debt_to_income": record["debt_to_income"],
                            "savings_rate": record["savings_rate"],
                            "interest_burden": record["interest_burden"],
                            "badges": record["badges"],
                            "created_at": record["created_at"],
                            "cta_url": url_for('financial_health.dashboard', _external=True)
                        },
                        lang=lang
                    )
                except ValueError as ve:
                    current_app.logger.error(f"Configuration error in email sending: {str(ve)}")
                    flash(trans("financial_health_email_config_error", lang=lang, default="Email configuration error"), "warning")
                except RuntimeError as re:
                    current_app.logger.error(f"Runtime error in email sending: {str(re)}")
                    flash(trans("financial_health_email_failed", lang=lang), "warning")
                except Exception as email_error:
                    current_app.logger.error(f"Unexpected error in email sending: {str(email_error)}")
                    flash(trans("financial_health_email_failed", lang=lang), "warning")

            session.pop('health_step1', None)
            session.pop('health_step2', None)
            current_app.logger.info("Financial health assessment completed successfully")
            flash(trans("financial_health_health_completed_success", lang=lang), "success")
            return redirect(url_for('financial_health.dashboard'))
        return render_template('health_score_step3.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Unexpected error in step3: {str(e)}")
        flash(trans("financial_health_unexpected_error", lang=lang), "danger")
        return render_template('health_score_step3.html', form=form, trans=trans, lang=lang), 500

@financial_health_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Display financial health dashboard with comparison to others."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    current_app.logger.info(f"Starting dashboard for session {session['sid']}")
    try:
        required_fields = ['score', 'income', 'expenses', 'debt', 'interest_rate', 'debt_to_income', 'savings_rate']

        health_record = session.get('health_record', {})
        current_app.logger.debug(f"Session health_record: {health_record}")
        if not health_record:
            financial_health_storage = current_app.config['STORAGE_MANAGERS']['financial_health']
            stored_records = financial_health_storage.filter_by_session(session['sid'])
            current_app.logger.debug(f"Raw stored records for current session: {stored_records}")
            if not stored_records:
                current_app.logger.warning("No records found for this session in storage")
                latest_record = {}
                records = []
            else:
                final_record = None
                for record in sorted(stored_records, key=lambda x: x.get('timestamp', ''), reverse=True):
                    if record.get('data') and record['data'].get('step') == 3:
                        final_record = record
                        break
                if not final_record:
                    final_record = sorted(stored_records, key=lambda x: x.get('timestamp', ''), reverse=True)[0]
                    current_app.logger.warning("No step 3 record found for session, using absolute latest record.")

                if final_record.get('data') and 'step' in final_record['data']:
                    latest_record = final_record['data'].get('data', {})
                else:
                    latest_record = final_record.get('data', {})

                for field in required_fields:
                    if field not in latest_record or latest_record[field] is None:
                        current_app.logger.warning(f"Missing or None field '{field}' in latest record for session {session['sid']}: {latest_record}. Setting to 0.")
                        latest_record[field] = 0
                    elif not isinstance(latest_record[field], (int, float)):
                        try:
                            latest_record[field] = float(latest_record[field])
                            current_app.logger.debug(f"Converted '{field}' to float: {latest_record[field]}")
                        except (ValueError, TypeError):
                            current_app.logger.warning(f"Invalid type for '{field}' in latest record for session {session['sid']}: {type(latest_record[field])}, setting to 0.")
                            latest_record[field] = 0
                records = [(final_record.get('id', str(uuid.uuid4())), latest_record)]
                current_app.logger.debug(f"Processed user records from storage: {records}")
        else:
            latest_record = health_record
            for field in required_fields:
                if field not in latest_record or latest_record[field] is None:
                    current_app.logger.warning(f"Missing or None field '{field}' in session health_record: {latest_record}. Setting to 0.")
                    latest_record[field] = 0
                elif not isinstance(latest_record[field], (int, float)):
                    try:
                        latest_record[field] = float(latest_record[field])
                        current_app.logger.debug(f"Converted '{field}' to float: {latest_record[field]}")
                    except (ValueError, TypeError):
                        current_app.logger.warning(f"Invalid type for '{field}' in session health_record: {type(latest_record[field])}, setting to 0.")
                        latest_record[field] = 0
            records = [(str(uuid.uuid4()), latest_record)]
            current_app.logger.debug(f"Processed user records from session: {records}")

        financial_health_storage = current_app.config['STORAGE_MANAGERS']['financial_health']
        all_records = financial_health_storage._read()
        current_app.logger.debug(f"All records from storage (before cleaning): {all_records}")
        
        cleaned_records = []
        for record_item in all_records:
            try:
                if record_item.get('data') and 'step' in record_item['data'] and record_item['data'].get('step') != 3:
                    continue
                
                data = record_item.get('data', {})
                if 'step' in data:
                    data = data.get('data', {})
                
                score = data.get('score')
                if score is None:
                    current_app.logger.warning(f"Record {record_item.get('id', 'N/A')} has no 'score' field. Skipping for comparison.")
                    continue
                if not isinstance(score, (int, float)):
                    try:
                        score = float(str(score).replace(',', ''))
                    except (ValueError, TypeError):
                        current_app.logger.warning(f"Record {record_item.get('id', 'N/A')} has invalid 'score' type: {type(score)}. Skipping for comparison.")
                        continue
                
                cleaned_records.append({
                    'id': record_item.get('id'),
                    'session_id': record_item.get('session_id'),
                    'timestamp': record_item.get('timestamp'),
                    'data': {'data': data}
                })
            except Exception as record_cleaning_error:
                current_app.logger.warning(f"Skipping invalid record during cleaning for comparison (ID: {record_item.get('id', 'N/A')}): {str(record_cleaning_error)}")
                continue
        
        current_app.logger.debug(f"Cleaned records for comparison: {cleaned_records}")
        
        total_users = len(cleaned_records)
        rank = 0
        average_score = 0
        
        if cleaned_records:
            all_scores_for_comparison = []
            for rec in cleaned_records:
                score_val = rec['data']['data'].get('score')
                if isinstance(score_val, (int, float)):
                    all_scores_for_comparison.append(score_val)
            
            if all_scores_for_comparison:
                all_scores_for_comparison.sort(reverse=True)
                
                user_score = latest_record.get("score", 0)
                
                rank = 1
                for s in all_scores_for_comparison:
                    if s > user_score:
                        rank += 1
                    else:
                        break
                
                average_score = sum(all_scores_for_comparison) / len(all_scores_for_comparison)
                current_app.logger.debug(f"Calculated user rank: {rank}, Average score of all users: {average_score}")
            else:
                current_app.logger.warning("No valid scores found in cleaned records for rank/average calculation.")
                rank = 0
                average_score = 0
        else:
            current_app.logger.info("No cleaned records available for comparison, rank and average score set to 0.")
            rank = 0
            average_score = 0

        insights = []
        tips = [
            trans("financial_health_tip_track_expenses", lang=lang),
            trans("financial_health_tip_ajo_savings", lang=lang),
            trans("financial_health_tip_pay_debts", lang=lang),
            trans("financial_health_tip_plan_expenses", lang=lang)
        ]
        
        if latest_record:
            try:
                if latest_record.get('debt_to_income', 0) > 40:
                    insights.append(trans("financial_health_insight_high_debt", lang=lang))
                if latest_record.get('savings_rate', 0) < 0:
                    insights.append(trans("financial_health_insight_negative_savings", lang=lang))
                elif latest_record.get('savings_rate', 0) >= 20:
                    insights.append(trans("financial_health_insight_good_savings", lang=lang))
                if latest_record.get('interest_burden', 0) > 10:
                    insights.append(trans("financial_health_insight_high_interest", lang=lang))
                
                if total_users >= 5:
                    if rank <= total_users * 0.1:
                        insights.append(trans("financial_health_insight_top_10", lang=lang))
                    elif rank <= total_users * 0.3:
                        insights.append(trans("financial_health_insight_top_30", lang=lang))
                    else:
                        insights.append(trans("financial_health_insight_below_30", lang=lang))
                else:
                    insights.append(trans("financial_health_insight_not_enough_users", lang=lang))

            except Exception as insight_error:
                current_app.logger.exception(f"Error generating insights: {str(insight_error)}")
                insights.append(trans("financial_health_insight_data_issues", lang=lang))
        else:
            insights.append(trans("financial_health_insight_no_data", lang=lang))

        progress_storage = current_app.config['STORAGE_MANAGERS'].get('progress')
        progress_records = []
        if progress_storage and 'sid' in session:
            try:
                progress_records = progress_storage.filter_by_session(session['sid'])
                current_app.logger.debug(f"Course progress records for session {session['sid']}: {progress_records}")
            except Exception as e:
                current_app.logger.warning(f"Failed to fetch progress records: {str(e)}")
                progress_records = []
        else:
            current_app.logger.warning("Progress storage not configured or session ID missing, skipping progress records")

        return render_template(
            'health_score_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            rank=rank,
            total_users=total_users,
            average_score=average_score,
            trans=trans,
            lang=lang,
            progress_records=progress_records
        )
    except Exception as e:
        current_app.logger.exception(f"Critical error in dashboard: {str(e)}")
        flash(trans("financial_health_dashboard_load_error", lang=lang), "danger")
        return render_template(
            'health_score_dashboard.html',
            records=[],
            latest_record={},
            insights=[trans("financial_health_insight_no_data", lang=lang)],
            tips=[
                trans("financial_health_tip_track_expenses", lang=lang),
                trans("financial_health_tip_ajo_savings", lang=lang),
                trans("financial_health_tip_pay_debts", lang=lang),
                trans("financial_health_tip_plan_expenses", lang=lang)
            ],
            rank=0,
            total_users=0,
            average_score=0,
            trans=trans,
            lang=lang,
            progress_records=[]
        ), 500
