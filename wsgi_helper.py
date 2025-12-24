import sys
import os

# --- PATH FINDER ---
# This block will search for 'app.py' and tell you where it is.
start_dir = '/home/divy123'
found_path = None

print(f"DEBUG: Searching for app.py in {start_dir}...", file=sys.stderr)

for root, dirs, files in os.walk(start_dir):
    if 'app.py' in files:
        found_path = root
        print(f"DEBUG: FOUND app.py in: {found_path}", file=sys.stderr)
        break

if found_path:
    project_home = found_path
    if project_home not in sys.path:
        sys.path = [project_home] + sys.path
    
    # Set environment variables
    os.environ['HEADLESS'] = 'true'
    
    try:
        from app import app as application
        print("DEBUG: Successfully imported app!", file=sys.stderr)
    except Exception as e:
        print(f"DEBUG: Found file but import failed: {e}", file=sys.stderr)
        raise e
else:
    print("DEBUG: CRITICAL - Could not find 'app.py' anywhere in /home/divy123/", file=sys.stderr)
    raise Exception("Could not find app.py")

