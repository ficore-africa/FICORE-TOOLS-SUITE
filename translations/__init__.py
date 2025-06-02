import logging
from flask import session, has_request_context, g, request  
from typing import Dict, Optional, Union

# Set up logger to match app.py
root_logger = logging.getLogger('ficore_app')
root_logger.setLevel(logging.DEBUG)

class SessionFormatter(logging.Formatter):
    def format(self, record):
        record.session_id = getattr(record, 'session_id', 'no_session_id')
        return super().format(record)

formatter = SessionFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s [session: %(session_id)s]')

class SessionAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs['extra'] = kwargs.get('extra', {})
        session_id = kwargs['extra'].get('session_id', 'no-session-id')
        if has_request_context():
            session_id = session.get('sid', 'no-session-id')
        kwargs['extra']['session_id'] = session_id
        return msg, kwargs

logger = SessionAdapter(root_logger, {})

# Import translation modules
try:
    from .translations_core import CORE_TRANSLATIONS as translations_core
    from .translations_quiz import QUIZ_TRANSLATIONS as translations_quiz
    from .translations_mailersend import MAILERSEND_TRANSLATIONS as translations_mailersend
    from .translations_bill import BILL_TRANSLATIONS as translations_bill
    from .translations_budget import BUDGET_TRANSLATIONS as translations_budget
    from .translations_dashboard import DASHBOARD_TRANSLATIONS as translations_dashboard
    from .translations_emergency_fund import EMERGENCY_FUND_TRANSLATIONS as translations_emergency_fund
    from .translations_financial_health import FINANCIAL_HEALTH_TRANSLATIONS as translations_financial_health
    from .translations_net_worth import NET_WORTH_TRANSLATIONS as translations_net_worth
    from .translations_learning_hub import LEARNING_HUB_TRANSLATIONS as translations_learning_hub
except ImportError as e:
    logger.error(f"Failed to import translation module: {str(e)}", exc_info=True)
    raise

# Map module names to translation dictionaries
translation_modules = {
    'core': translations_core,
    'quiz': translations_quiz,
    'mailersend': translations_mailersend,
    'bill': translations_bill,
    'budget': translations_budget,
    'dashboard': translations_dashboard,
    'emergency_fund': translations_emergency_fund,
    'financial_health': translations_financial_health,
    'net_worth': translations_net_worth,
    'learning_hub': translations_learning_hub
}

# Map key prefixes to module names
KEY_PREFIX_TO_MODULE = {
    'core_': 'core',
    'quiz_': 'quiz',
    'badge_': 'quiz',  # Route badge_ keys to QUIZ_TRANSLATIONS
    'mailersend_': 'mailersend',
    'bill_': 'bill',
    'budget_': 'budget',
    'dashboard_': 'dashboard',
    'emergency_fund_': 'emergency_fund',
    'financial_health_': 'financial_health',
    'net_worth_': 'net_worth',
    'learning_hub_': 'learning_hub'
}

# Quiz-specific keys without prefixes
QUIZ_SPECIFIC_KEYS = {'Yes', 'No', 'See Results'}

# Log loaded translations
for module_name, translations in translation_modules.items():
    for lang in ['en', 'ha']:
        lang_dict = translations.get(lang, {})
        logger.info(f"Loaded {len(lang_dict)} translations for module '{module_name}', lang='{lang}'")

def trans(key: str, lang: Optional[str] = None, **kwargs: str) -> str:
    """
    Translate a key using the appropriate module's translation dictionary.
    
    Args:
        key: The translation key (e.g., 'core_submit', 'quiz_yes', 'Yes').
        lang: Language code ('en', 'ha'). Defaults to session['lang'] or 'en'.
        **kwargs: String formatting parameters for the translated string.
    
    Returns:
        The translated string, falling back to English or the key itself if missing.
        Applies string formatting with kwargs if provided.
    
    Notes:
        - Uses session['lang'] if lang is None and request context exists.
        - Logs warnings for missing translations.
        - Uses g.logger if available, else the default logger.
    """
    current_logger = g.get('logger', logger) if has_request_context() else logger
    session_id = session.get('sid', 'no-session-id') if has_request_context() else 'no-session-id'

    # Default to session language or 'en'
    if lang is None:
        lang = session.get('lang', 'en') if has_request_context() else 'en'
    if lang not in ['en', 'ha']:
        current_logger.warning(f"Invalid language '{lang}', falling back to 'en'", extra={'session_id': session_id})
        lang = 'en'

    # Determine module based on key prefix or specific keys
    module_name = 'core'
    for prefix, mod in KEY_PREFIX_TO_MODULE.items():
        if key.startswith(prefix):
            module_name = mod
            break
    if key in QUIZ_SPECIFIC_KEYS and has_request_context() and '/quiz/' in request.path:
        module_name = 'quiz'

    module = translation_modules.get(module_name, translation_modules['core'])
    lang_dict = module.get(lang, {})

    # Get translation
    translation = lang_dict.get(key)

    # Fallback to English, then key
    if translation is None:
        en_dict = module.get('en', {})
        translation = en_dict.get(key, key)
        if translation == key:
            current_logger.warning(
                f"Missing translation for key='{key}' in module '{module_name}', lang='{lang}'",
                extra={'session_id': session_id}
            )

    # Apply string formatting
    try:
        return translation.format(**kwargs) if kwargs else translation
    except (KeyError, ValueError) as e:
        current_logger.error(
            f"Formatting failed for key '{key}', lang='{lang}', kwargs={kwargs}, error={str(e)}",
            extra={'session_id': session_id}
        )
        return translation

def get_translations(lang: Optional[str] = None) -> Dict[str, callable]:
    """
    Return a dictionary with a trans callable for the specified language.

    Args:
        lang: Language code ('en', 'ha'). Defaults to session['lang'] or 'en'.

    Returns:
        A dictionary with a 'trans' function that translates keys for the specified language.
    """
    if lang is None:
        lang = session.get('lang', 'en') if has_request_context() else 'en'
    if lang not in ['en', 'ha']:
        logger.warning(f"Invalid language '{lang}', falling back to 'en'")
        lang = 'en'
    return {
        'trans': lambda key, **kwargs: trans(key, lang=lang, **kwargs)
    }

__all__ = ['trans']
