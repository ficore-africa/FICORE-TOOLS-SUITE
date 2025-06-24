
✅ Deployment Fixes to Remember'

Keep the Jinja2 filters (format_currency, format_date, etc.) in app.py as they are.
Add the corresponding Python functions (format_currency, format_date) to utils.py to resolve the ImportError in users/routes.py.
Use a raw string (r) for the regex pattern in app.py to eliminate the SyntaxWarning for the email pattern in the setup_database function.

1. MongoDB Connection Fix
- Use this format for MongoDB Atlas URI (avoid conflicting SSL params):
  
  mongodb+srv://<username>:<password>@<cluster>.mongodb.net/<dbname>?retryWrites=true&w=majority&tlsAllowInvalidCertificates=true
  
- Avoid mixing ssl= and tls=; use *only tlsAllowInvalidCertificates=true* during development if needed.
- Ensure IP access is allowed in MongoDB Atlas.

2. Flask-Babel 4.0.0 Compatibility Fix
- DO NOT use the deprecated @babel.localeselector decorator.
- Instead, define a plain function and assign it directly:
  python
  def get_locale():
      return session.get('lang', request.accept_languages.best_match(['en', 'ha'], default='en'))

  babel.locale_selector = get_locale
  

- Place this block *right after babel = Babel(app)* in your main app.py.
