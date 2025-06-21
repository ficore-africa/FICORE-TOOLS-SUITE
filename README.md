
✅ Deployment Fixes to Remember

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
