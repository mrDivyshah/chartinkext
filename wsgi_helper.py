import sys
import os

# Add your project directory to the sys.path
project_home = '/home/yourusername/mysite'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Set environment variables if needed (or set them in the dashboard)
os.environ['HEADLESS'] = 'true'

# Import flask app but need to call it "application" for WSGI to work
from app import app as application
