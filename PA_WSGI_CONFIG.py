import sys
import os

# 1. CHANGE THIS PATH to point to your project folder
#    It must be the folder containing 'app.py'
#    Example: '/home/divy123/chartink_project/flask_app'
project_home = '/home/divy123/mysite/flask_app' 

# 2. Add to python path
if project_home not in sys.path:
    sys.path.append(project_home)

# 3. Import the flask app
#    Ensure 'app.py' exists in 'project_home'
from app import app as application

# Optional: Set environment variable if needed manually
# os.environ['PYTHONANYWHERE_DOMAIN'] = 'divy123.pythonanywhere.com'
