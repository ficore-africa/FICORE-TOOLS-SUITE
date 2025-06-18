import logging
import os
import smtplib
import requests
from email.mime.text import MIMEText
from flask import Flask, render_template, current_app
from typing import Dict, Optional
from translations import trans

# Email configuration dictionary with provider-specific templates
EMAIL_CONFIG = {
    "financial_health": {
        "subject_key": "financial_health_financial_health_report",
        "template": {
            "mailersend": "health_score_email.html",
            "gmail": "health_score_email_gmail.html"
        }
    },
    "budget": {
        "subject_key": "budget_plan_summary",
        "template": {
            "mailersend": "budget_email.html",
            "gmail": "budget_email_gmail.html"
        }
    },
    "quiz": {
        "subject_key": "quiz_results_summary",
        "template": {
            "mailersend": "quiz_email.html",
            "gmail": "quiz_email_gmail.html"
        }
    },
    "bill_reminder": {
        "subject_key": "bill_payment_reminder",
        "template": {
            "mailersend": "bill_reminder.html",
            "gmail": "bill_reminder_gmail.html"
        }
    },
    "net_worth": {
        "subject_key": "net_worth_net_worth_summary",
        "template": {
            "mailersend": "net_worth_email.html",
            "gmail": "net_worth_email.html"
        }
    },
    "emergency_fund": {
        "subject_key": "emergency_fund_email_subject",
        "template": {
            "mailersend": "emergency_fund.html",
            "gmail": "emergency_fund.html"
        }
    },
    "learning_hub_lesson_completed": {
        "subject_key": "learning_hub_lesson_completed_subject",
        "template": {
            "mailersend": "learning_hub_lesson_completed.html",
            "gmail": "learning_hub_lesson_completed.html"
        }
    }
}

def init_email_config(app: Flask, logger: logging.LoggerAdapter):
    """Validate email provider configuration at startup."""
    mailersend_enabled = bool(os.getenv('MAILERSEND_API_TOKEN') and os.getenv('MAILERSEND_FROM_EMAIL'))
    gmail_enabled = bool(os.getenv('GMAIL_EMAIL') and os.getenv('GMAIL_PASSWORD'))
    if not (mailersend_enabled or gmail_enabled):
        logger.warning("No email providers configured: Missing MailerSend or Gmail credentials")
    else:
        logger.info(f"Email providers configured: MailerSend={mailersend_enabled}, Gmail={gmail_enabled}")

def send_email(
    app: Flask,
    logger: logging.LoggerAdapter,
    to_email: str,
    subject: str,
    template_key: str,
    data: Dict = None,
    lang: str = 'en',
    job_id: Optional[str] = None
) -> None:
    """
    Send an email using a prioritized list of providers (MailerSend, Gmail) with provider-specific templates.

    Args:
        app: Flask application instance for context.
        logger: Logger instance with SessionAdapter for session-aware logging.
        to_email: Recipient's email address.
        subject: Email subject.
        template_key: Key in EMAIL_CONFIG (e.g., 'budget', 'quiz').
        data: Data to pass to the template for rendering. Defaults to empty dict if None.
        lang: Language code ('en' or 'ha'). Defaults to 'en'.
        job_id: Optional job ID for scheduled tasks to replace session ID in logs.

    Raises:
        ValueError: If API token, from email, template, or template_key is invalid.
        RuntimeError: If all providers fail to send the email.

    Notes:
        - Requires environment variables:
          - MAILERSEND_API_TOKEN, MAILERSEND_FROM_EMAIL for MailerSend.
          - GMAIL_EMAIL, GMAIL_PASSWORD (must be an App Password for Gmail with 2FA).
        - Uses provider-specific templates from EMAIL_CONFIG.
        - Logs errors with job_id or session_id for debugging.
        - Includes retry logic for API/network failures and provider fallback.
    """
    session_id = job_id or 'no-session-id'
    logger.info(f"send_email called with: to_email={to_email}, subject={subject}, template_key={template_key}, data_type={type(data)}, data={data}, lang={lang}", extra={'session_id': session_id})

    # Validate language
    if lang not in ['en', 'ha']:
        logger.warning(f"Invalid language '{lang}', falling back to 'en'", extra={'session_id': session_id})
        lang = 'en'

    # Ensure data is a dictionary
    data = data or {}
    if not isinstance(data, dict):
        logger.error(f"Data must be a dictionary, got {type(data)}: {data}", extra={'session_id': session_id})
        raise ValueError(f"Data must be a dictionary, got {type(data)}")

    # Validate template_key
    if template_key is None:
        logger.error("template_key must be provided", extra={'session_id': session_id})
        raise ValueError("template_key must be provided")

    config = EMAIL_CONFIG.get(template_key)
    if not config:
        logger.error(f"Invalid template_key '{template_key}'", extra={'session_id': session_id})
        raise ValueError(f"Template key '{template_key}' not found in EMAIL_CONFIG. Valid keys: {list(EMAIL_CONFIG.keys())}")

    # Validate environment variables
    mailersend_enabled = bool(os.getenv('MAILERSEND_API_TOKEN') and os.getenv('MAILERSEND_FROM_EMAIL'))
    gmail_enabled = bool(os.getenv('GMAIL_EMAIL') and os.getenv('GMAIL_PASSWORD'))
    if not (mailersend_enabled or gmail_enabled):
        logger.error("No email providers configured: missing MailerSend or Gmail credentials", extra={'session_id': session_id})
        raise ValueError("No email providers configured")

    # Define provider priority
    providers = ['mailersend', 'gmail']
    last_error = None

    for provider in providers:
        if (provider == 'mailersend' and not mailersend_enabled) or (provider == 'gmail' and not gmail_enabled):
            logger.info(f"Skipping provider {provider} due to missing credentials", extra={'session_id': session_id})
            continue

        try:
            # Select template based on provider
            template_name = config["template"].get(provider, config["template"].get('mailersend'))
            if not template_name.endswith('.html'):
                template_name += '.html'
            # Assume template is in templates/ or templates/bill/ for bill_reminder
            template_path = os.path.join(current_app.template_folder, template_name)
            if template_key == 'bill_reminder':
                # Check bill blueprint folder
                bill_template_path = os.path.join(current_app.template_folder, 'bill', template_name)
                if os.path.exists(bill_template_path):
                    template_path = bill_template_path
            if not os.path.exists(template_path):
                raise ValueError(f"Template {template_name} for provider {provider} not found at {template_path}")

            # Render email template
            with app.app_context():
                try:
                    html_content = render_template(template_name, **data, lang=lang)
                    logger.info(f"Template {template_name} rendered successfully, content length: {len(html_content)}", extra={'session_id': session_id})
                except KeyError as e:
                    logger.warning(f"Missing key {e} in data for template {template_name}, using empty string", extra={'session_id': session_id})
                    data[str(e)] = ""
                    html_content = render_template(template_name, **data, lang=lang)
                except Exception as e:
                    logger.error(f"Cannot render email template {template_name}: {str(e)}", extra={'session_id': session_id})
                    raise RuntimeError(f"Cannot render email template {template_name}: {str(e)}")

            if provider == 'mailersend':
                api_token = os.getenv('MAILERSEND_API_TOKEN')
                from_email = os.getenv('MAILERSEND_FROM_EMAIL')
                url = "https://api.mailersend.com/v1/email"
                headers = {
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "from": {"email": from_email, "name": "FiCore Africa"},
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "html": html_content
                }

                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    try:
                        response = requests.post(url, json=payload, headers=headers, timeout=10)
                        if 200 <= response.status_code < 300:
                            logger.info(f"Email sent successfully to {to_email} via {provider}", extra={'session_id': session_id, 'provider': provider})
                            return
                        else:
                            raise RuntimeError(f"MailerSend API error: {response.status_code} {response.text}")
                    except requests.RequestException as e:
                        if attempt < max_retries:
                            delay = 2 ** attempt
                            logger.warning(f"Network error sending email to {to_email} via {provider}: {str(e)}. Retrying... (attempt {attempt})", extra={'session_id': session_id, 'provider': provider})
                            continue
                        raise

            elif provider == 'gmail':
                smtp_user = os.getenv('GMAIL_EMAIL')
                smtp_password = os.getenv('GMAIL_PASSWORD')
                msg = MIMEText(html_content, 'html')
                msg['Subject'] = subject
                msg['From'] = f"FiCore Africa <{smtp_user}>"
                msg['To'] = to_email

                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    try:
                        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                            server.login(smtp_user, smtp_password)
                            server.send_message(msg)
                        logger.info(f"Email sent successfully to {to_email} via {provider}", extra={'session_id': session_id, 'provider': provider})
                        return
                    except smtplib.SMTPException as e:
                        if attempt < max_retries:
                            delay = 2 ** attempt
                            logger.warning(f"Gmail SMTP error sending email to {to_email}: {str(e)}. Retrying... (attempt {attempt})", extra={'session_id': session_id, 'provider': provider})
                            continue
                        raise RuntimeError(f"Gmail SMTP error: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to send email to {to_email} via {provider}: {str(e)}", extra={'session_id': session_id, 'provider': provider})
            last_error = e
            continue

    logger.error(f"All providers failed to send email to {to_email}", extra={'session_id': session_id, 'providers_attempted': providers})
    raise RuntimeError(f"All email providers failed: {str(last_error)}")
