import logging
import os
import smtplib
import requests
from email.mime.text import MIMEText
from flask import Flask, session, has_request_context, render_template
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
            "gmail": "net_worth_email_gmail.html"
        }
    },
    "emergency_fund": {
        "subject_key": "emergency_fund_email_subject",
        "template": {
            "mailersend": "emergency_fund_email.html",
            "gmail": "emergency_fund_email_gmail.html"
        }
    },
    "learning_hub_lesson_completed": {
        "subject_key": "learning_hub_lesson_completed_subject",
        "template": {
            "mailersend": "learning_hub_lesson_completed.html",
            "gmail": "learning_hub_lesson_completed_gmail.html"
        }
    }
}

def send_email(
    app: Flask,
    logger: logging.LoggerAdapter,
    to_email: str,
    subject: str,
    template_key: Optional[str] = None,
    data: Dict = None,
    lang: Optional[str] = None,
    template_name: Optional[str] = None
) -> None:
    """
    Send an email using a prioritized list of providers (MailerSend, Gmail) with provider-specific templates.

    Args:
        app: Flask application instance for context.
        logger: Logger instance with SessionAdapter for session-aware logging.
        to_email: Recipient's email address.
        subject: Email subject.
        template_key: Key in EMAIL_CONFIG (e.g., 'budget', 'quiz'). Preferred argument.
        data: Data to pass to the template for rendering. Defaults to empty dict if None.
        lang: Language code ('en' or 'ha'). Defaults to session['lang'] or 'en'.
        template_name: Deprecated. Fallback for template_key. Issues a warning if used.

    Raises:
        ValueError: If API token, from email, template, or template_key/template_name is invalid.
        RuntimeError: If all providers fail to send the email.

    Notes:
        - Prioritizes template_key over template_name. Warns if template_name is used.
        - Requires environment variables: MAILERSEND_API_TOKEN, MAILERSEND_FROM_EMAIL,
          GMAIL_SMTP_USER, GMAIL_SMTP_PASSWORD.
        - Uses provider-specific templates from EMAIL_CONFIG, falling back to 'mailersend' template if needed.
        - Logs errors with session ID and provider details for debugging.
        - Includes retry logic for API/network failures and provider fallback.
    """
    session_id = session.get('sid', 'no-session-id') if has_request_context() else 'no-session-id'
    logger.info(f"send_email called with: to_email={to_email}, subject={subject}, template_key={template_key}, template_name={template_name}, data_type={type(data)}, data={data}, lang={lang}", extra={'session_id': session_id})

    # Default language from session
    if lang is None:
        lang = session.get('lang', 'en') if has_request_context() else 'en'
    if lang not in ['en', 'ha']:
        logger.warning(f"Invalid language '{lang}', falling back to 'en'", extra={'session_id': session_id})
        lang = 'en'

    # Ensure data is a dictionary
    data = data or {}
    if not isinstance(data, dict):
        logger.error(f"Data must be a dictionary, got {type(data)}: {data}", extra={'session_id': session_id})
        raise ValueError(f"Data must be a dictionary, got {type(data)}")

    # Prioritize template_key, fall back to template_name
    if template_key is None and template_name is None:
        logger.error("Neither template_key nor template_name provided", extra={'session_id': session_id})
        raise ValueError("Either template_key or template_name must be provided")
    
    if template_key is None and template_name is not None:
        logger.warning(f"Deprecated argument 'template_name' used: {template_name}. Use 'template_key' instead.", extra={'session_id': session_id})
        template_key = template_name

    # Validate template_key type
    if not isinstance(template_key, str):
        logger.error(f"template_key must be a string, got {type(template_key)}: {template_key}", extra={'session_id': session_id})
        raise ValueError(f"template_key must be a string, got {type(template_key)}")

    config = EMAIL_CONFIG.get(template_key)
    if not config:
        logger.error(f"Invalid template_key '{template_key}'", extra={'session_id': session_id})
        raise ValueError(f"Template key '{template_key}' not found in EMAIL_CONFIG. Valid keys: {list(EMAIL_CONFIG.keys())}")

    # Define provider priority (extendable for future providers)
    providers = ['mailersend', 'gmail']
    last_error = None

    for provider in providers:
        try:
            # Select template based on provider (fallback to mailersend template if not specified)
            template_name = config["template"].get(provider, config["template"].get('mailersend', config["template"])) if isinstance(config["template"], dict) else config["template"]
            if not template_name.endswith('.html'):
                template_name += '.html'
            template_path = os.path.join(app.template_folder, template_name)
            logger.info(f"Using template: {template_name} at {template_path} for provider {provider}", extra={'session_id': session_id})
            if not os.path.exists(template_path):
                raise ValueError(f"Template {template_name} for provider {provider} not found at {template_path}")

            # Render email template with fallback for missing keys
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
                # Validate MailerSend environment variables
                api_token = os.environ.get('MAILERSEND_API_TOKEN')
                from_email = os.environ.get('MAILERSEND_FROM_EMAIL')
                if not api_token or not from_email:
                    raise ValueError(f"MailerSend {'API token' if not api_token else 'from email'} not set")

                # Configure MailerSend API request
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

                # Send with retry logic
                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    try:
                        response = requests.post(url, json=payload, headers=headers, timeout=10)
                        if 200 <= response.status_code < 300:
                            logger.info(f"Email sent successfully to {to_email} via {provider}", extra={'session_id': session_id, 'provider': provider})
                            return  # Success, exit
                        else:
                            raise RuntimeError(f"MailerSend API error: {response.status_code} {response.text}")
                    except requests.RequestException as e:
                        if attempt < max_retries:
                            delay = 2 ** attempt
                            logger.warning(f"Network error sending email to {to_email} via {provider}: {str(e)}. Retrying... (attempt {attempt})", extra={'session_id': session_id, 'provider': provider})
                            continue
                        raise

            elif provider == 'gmail':
                # Validate Gmail environment variables
                smtp_user = os.environ.get('GMAIL_SMTP_USER')
                smtp_password = os.environ.get('GMAIL_SMTP_PASSWORD')
                if not smtp_user or not smtp_password:
                    raise ValueError(f"Gmail {'SMTP user' if not smtp_user else 'SMTP password'} not set")

                # Configure Gmail SMTP
                msg = MIMEText(html_content, 'html')
                msg['Subject'] = subject
                msg['From'] = f"FiCore Africa <{smtp_user}>"
                msg['To'] = to_email

                # Send via Gmail SMTP
                try:
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                        server.login(smtp_user, smtp_password)
                        server.send_message(msg)
                    logger.info(f"Email sent successfully to {to_email} via {provider}", extra={'session_id': session_id, 'provider': provider})
                    return  # Success, exit
                except smtplib.SMTPException as e:
                    raise RuntimeError(f"Gmail SMTP error: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to send email to {to_email} via {provider}: {str(e)}", extra={'session_id': session_id, 'provider': provider})
            last_error = e
            continue

    # If all providers fail
    logger.error(f"All providers failed to send email to {to_email}", extra={'session_id': session_id, 'providers_attempted': providers})
    raise RuntimeError(f"All email providers failed: {str(last_error)}")
