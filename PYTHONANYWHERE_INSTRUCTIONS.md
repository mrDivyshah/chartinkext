# Deploying to PythonAnywhere

## 1. Uploading Code
1.  Open a **Bash** console on PythonAnywhere.
2.  Clone your repository (or upload a zip if not using git):
    ```bash
    git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git mysite
    ```
    *(Replace with your actual repo URL. If you uploaded a zip, unzip it into a folder).*

## 2. Set up Virtual Environment
Run these commands in the Bash console:

```bash
cd mysite
mkvirtualenv --python=/usr/bin/python3.10 myenv
pip install -r requirements.txt
```

## 3. Web App Setup
1.  Go to the **Web** tab in the PythonAnywhere dashboard.
2.  **Add a new web app**.
    *   Select **Manual configuration** (since we are setting up a custom environment).
    *   Select **Python 3.10**.
3.  **Virtualenv**:
    *   In the Virtualenv section, enter the path: `/home/yourusername/.virtualenvs/myenv`
    *   *(Replace `yourusername` with your actual PythonAnywhere username)*.

## 4. WSGI Configuration
1.  In the **Code** section of the Web tab, click on the **WSGI configuration file** link (e.g., `/var/www/yourusername_pythonanywhere_com_wsgi.py`).
2.  Delete everything in that file.
3.  Copy and paste the code from `wsgi_helper.py` in your project.
4.  **Important**: Update the `project_home` variable in that code to point to your actual project folder:
    ```python
    project_home = '/home/yourusername/mysite' 
    ```

## 5. Reload
1.  Go back to the **Web** tab.
2.  Click the big green **Reload** button.
3.  Visit your site URL!

## Troubleshooting
*   **Whitelisting**: If scraping fails with connection errors and you are on a **Free** account, `chartink.com` might not be allow-listed. You may need to upgrade to the $5/mo "Hacker" plan to access external sites freely.
*   **Chrome Issues**: PythonAnywhere has Google Chrome installed. Your app uses `webdriver-manager` which usually works, but if it fails, you might need to manually specify the path to the system's chrome.
    *   Check `error_log` in the Web tab if the app crashes.
