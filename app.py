import threading
import uuid
import os
import json
import secrets # Added
import time
import base64
import requests
from io import BytesIO
from datetime import datetime
import asyncio

from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from PIL import Image as PILImage
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from telegram import Bot

# --- Configuration ---
from flask_mail import Mail, Message # Added

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chartink_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail Configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') # Setup Env Var
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD') # Setup Env Var
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

db = SQLAlchemy(app)
mail = Mail(app) # Init Mail
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False) # New
    password_hash = db.Column(db.String(200), nullable=False)
    telegram_bot_token = db.Column(db.String(200), nullable=True)
    telegram_chat_id = db.Column(db.String(100), nullable=True)
    recovery_code = db.Column(db.String(50), nullable=True) # New column
    presets = db.relationship('ScanPreset', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ScanPreset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    url = db.Column(db.String(1000), nullable=False)
    # Storing last used settings for this preset
    period = db.Column(db.String(50), default='weekly')
    range_val = db.Column(db.String(50), default='1 year')
    moving_average = db.Column(db.Boolean, default=True) # Deprecated
    ma_config = db.Column(db.Text, nullable=True) # Stores JSON string

# --- Global Job Store (In-Memory) ---
jobs = {}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Helper Functions ---

def web_driver():
    options = webdriver.ChromeOptions()
    options.page_load_strategy = 'eager' # Don't wait for full page load (images, css)
    options.add_argument("--verbose")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # Check for PythonAnywhere environment
    if 'PYTHONANYWHERE_DOMAIN' in os.environ:
        options.add_argument('--headless')
        
        # Try finding the binary
        paths = ["/usr/bin/chromium", "/usr/bin/chromium-browser"]
        found_bin = None
        for p in paths:
            if os.path.exists(p):
                found_bin = p
                break
        
        if found_bin:
            options.binary_location = found_bin
        
        try:
            service = Service("/usr/bin/chromedriver")
            driver = webdriver.Chrome(service=service, options=options)
            return driver
        except Exception as e:
            print(f"Failed to use system chromedriver: {e}")
            # Do NOT pass here, return None or let it fail, 
            # because fallback to webdriver_manager will definitely fail on PA
            pass

    # Docker / Local Headless
    if os.path.exists('/.dockerenv') or os.environ.get('HEADLESS', 'false').lower() == 'true':
        options.add_argument('--headless=new')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--disable-extensions')
        print("Running in Headless mode (Docker/Env detected)")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"Error setting up driver: {e}")
        raise e

async def send_telegram_pdf(token, chat_id, pdf_bytes, filename):
    try:
        bot = Bot(token=token)
        await bot.send_document(chat_id=chat_id, document=pdf_bytes, filename=filename, caption="Here is your Chartink Scan PDF.")
    except Exception as e:
        print(f"Telegram Error: {e}")

def get_url_and_index(driver):
    results = []
    # Logic from previous robust implementation
    while True:
        try:
            # Wait for table
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Stock Name')]"))
            )

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            links = soup.find_all('a', href=True)
            page_links = []
            for link in links:
                href = link.get('href')
                if 'fundamentals' in href:
                    href = href.replace('fundamentals', 'stocks')
                    full_link = f"https://chartink.com{href}"
                    if full_link not in results and full_link not in page_links:
                         page_links.append(full_link)
            
            # Check for empty scrape on subsequent pages
            if not page_links and results:
                pass # Retrying implicitly or break

            results.extend(page_links)
            print(f"Found {len(page_links)} links on this page. Total: {len(results)}")

            # Pagination Logic
            try:
                current_first_stock = ""
                try:
                    first_row_link = driver.find_element(By.XPATH, "//table[contains(@id, 'DataTables_Table')]//tbody//tr[1]//a[contains(@href, 'fundamentals')]")
                    current_first_stock = first_row_link.text
                except:
                    pass

                # Find Next button
                next_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Next')]")
                
                if next_buttons:
                    btn = next_buttons[0]
                    if btn.get_attribute('disabled') is not None:
                        break
                    
                    driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    driver.execute_script("arguments[0].click();", btn)
                    
                    try:
                        if current_first_stock:
                             WebDriverWait(driver, 10).until(
                                lambda d: d.find_element(By.XPATH, "//table[contains(@id, 'DataTables_Table')]//tbody//tr[1]//a[contains(@href, 'fundamentals')]").text != current_first_stock
                            )
                        else:
                             time.sleep(0.5)
                    except Exception as e:
                        pass
                else:
                    break
            except Exception as e:
                break

        except Exception as e:
            print("Error scraping URL:", e)
            break
    return results

def get_image_from_link(driver, url, period, s_range, moving_averages):
    try:
        driver.get(url)
        # Select period
        if period:
            try:
                period_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, f"//button[contains(text(), '{period}')]"))
                )
                period_btn.click()
            except:
                pass 
        
        # Determine the chart element ID
        # Chartink usually renders the main chart in #ci_layout or #img_chart
        # We wait for the chart image/container specifically
        
        chart_element = None
        try:
            # Wait for the specific chart layout or image to be visible
            chart_element = WebDriverWait(driver, 10).until(
                 EC.visibility_of_element_located((By.ID, 'ci_layout'))
            )
        except:
             try:
                 chart_element = driver.find_element(By.TAG_NAME, 'body')
             except:
                 pass

        if not chart_element:
            return None, None
            
        # Optional: A very short buffer for rendering final touches if eager load was too fast
        time.sleep(0.5) 
        
        # Get Company Name
        company_name = "Unknown"
        try:
            company_name = driver.find_element(By.XPATH, "//h1").text.strip()
        except:
             pass

        screenshot = chart_element.screenshot_as_base64
        return company_name, screenshot

    except Exception as e:
        print(f"Error getting image for {url}: {e}")
        return None, None

def generate_pdf(data):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_width = A4[0] 

    for item in data:
        company_name = item['company_name']
        image = item['image']
        
        img_buffer = BytesIO()
        image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        margin = 20
        draw_width = page_width - (margin * 2)
        
        img_width, img_height = image.size
        aspect_ratio = img_height / img_width
        draw_height = draw_width * aspect_ratio
        
        total_page_height = 50 + draw_height + 20
        c.setPageSize((page_width, total_page_height))
        
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(page_width / 2, total_page_height - 35, company_name)
        c.drawImage(ImageReader(img_buffer), margin, 20, width=draw_width, height=draw_height)
        c.showPage()

    c.save()
    return buffer.getvalue()

def process_job(job_id, screener_url, period, s_range, moving_averages, user_config):
    jobs[job_id]['status'] = 'running'
    jobs[job_id]['canceled'] = False
    
    processed_data = [] # Accumulate data
    urls = []
    
    # Attempt to get URLs first
    driver = None
    try:
        driver = web_driver()
        driver.get(screener_url)
        jobs[job_id]['status'] = 'scraping_urls'
        urls = get_url_and_index(driver)
        jobs[job_id]['total'] = len(urls)
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = f"URL Scraping Failed: {str(e)}"
        if driver: driver.quit()
        return
    finally:
        if driver: driver.quit()

    if not urls:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = 'No stocks found.'
        return

    # Image Processing Loop with Auto-Recovery
    jobs[job_id]['status'] = 'fetching_charts'
    current_index = 0
    max_retries = 5 # Try to recover driver crashes up to 5 times
    retry_count = 0
    
    while current_index < len(urls):
        if jobs[job_id].get('canceled'):
            break

        if retry_count >= max_retries:
            print(f"Max retries reached for job {job_id}")
            break

        driver = None
        try:
            driver = web_driver()
            
            # Inner loop for processing
            while current_index < len(urls):
                if jobs[job_id].get('canceled'):
                     break
                
                url = urls[current_index]
                jobs[job_id]['current_company'] = url # Update status
                
                # Fetch Image
                company_name, img_data_base64 = get_image_from_link(driver, url, period, s_range, moving_averages)
                
                if company_name and img_data_base64:
                    img_data = base64.b64decode(img_data_base64)
                    image = PILImage.open(BytesIO(img_data))
                    processed_data.append({"company_name": company_name, "image": image})
                    jobs[job_id]['current_company'] = company_name # Better name
                
                current_index += 1
                jobs[job_id]['processed'] = current_index
        
        except Exception as e:
            print(f"Driver crashed/error at index {current_index}: {e}. Restarting driver...")
            retry_count += 1
            # We do NOT increment current_index here, so we retry the current URL
            time.sleep(3) # Cooldown
        finally:
            if driver: 
                try: 
                    driver.quit()
                except: 
                    pass
    
    # Completion Handling
    if not processed_data:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = 'Job stopped or no data collected.' if jobs[job_id].get('canceled') else 'No charts fetched.'
        return

    jobs[job_id]['status'] = 'generating_pdf'
    try:
        pdf_bytes = generate_pdf(processed_data)
        jobs[job_id]['result'] = pdf_bytes
        jobs[job_id]['status'] = 'completed' if not jobs[job_id].get('canceled') else 'stopped' # allow download even if stopped
        
        # --- Telegram Integration ---
        token = user_config.get('tg_token')
        chat_id = user_config.get('tg_chat_id')
        if token and chat_id:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                fname = f"Chartink_Scan_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                loop.run_until_complete(send_telegram_pdf(token, chat_id, pdf_bytes, fname))
                loop.close()
                jobs[job_id]['telegram_sent'] = True
            except Exception as e:
                print(f"Failed to send telegram: {e}")

    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = f"PDF Gen Error: {str(e)}"

# --- Routes ---

@app.route('/stop_job/<job_id>', methods=['POST'])
@login_required
def stop_job(job_id):
    if job_id in jobs:
        jobs[job_id]['canceled'] = True
        return jsonify({'success': True})
    return jsonify({'error': 'Job not found'}), 404

@app.route('/')
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return render_template('index.html', user=current_user)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter((User.username==username) | (User.email==email)).first():
            flash('Username or Email already exists')
            return redirect(url_for('register'))
        
        # Generate backup recovery code
        recovery_code = secrets.token_hex(4).upper()
        
        new_user = User(username=username, email=email, recovery_code=recovery_code)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        flash(f'Registration Successful! Backup Recovery Code: {recovery_code}')
        return redirect(url_for('home'))
        
    return render_template('register.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        # Step 1: Request Code
        if 'request_code' in request.form:
            email = request.form.get('email')
            user = User.query.filter_by(email=email).first()
            if user:
                # Generate temporary reset code (simple 6 digit)
                code = str(secrets.randbelow(1000000)).zfill(6)
                user.recovery_code = code # Temporarily overwrite
                db.session.commit()
                
                try:
                    msg = Message("Password Reset Request", recipients=[email])
                    msg.body = f"Your Password Reset Code is: {code}"
                    mail.send(msg)
                    flash('Reset code sent to your email.')
                    return render_template('forgot_password.html', step='verify', email=email)
                except Exception as e:
                    print(e)
                    flash('Error sending email. Check server logs.')
            else:
                flash('Email not found.')
        
        # Step 2: Verify and Reset
        elif 'verify_code' in request.form:
            email = request.form.get('email')
            code = request.form.get('code')
            new_pass = request.form.get('new_password')
            
            user = User.query.filter_by(email=email).first()
            if user and user.recovery_code == code:
                user.set_password(new_pass)
                user.recovery_code = secrets.token_hex(4).upper() # Reset/Rotate
                db.session.commit()
                flash('Password reset successful! Please login.')
                return redirect(url_for('login'))
            else:
                flash('Invalid code.')
                return render_template('forgot_password.html', step='verify', email=email)
            
    return render_template('forgot_password.html', step='request')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/api/update_settings', methods=['POST'])
@login_required
def update_settings():
    data = request.json
    current_user.telegram_bot_token = data.get('telegram_bot_token')
    current_user.telegram_chat_id = data.get('telegram_chat_id')
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/presets', methods=['GET', 'POST'])
@login_required
def handle_presets():
    if request.method == 'POST':
        data = request.json
        
        ma_config_json = None
        if data.get('moving_averages'):
            ma_config_json = json.dumps(data['moving_averages'])

        preset = ScanPreset(
            user_id=current_user.id,
            title=data['title'],
            description=data.get('description', ''),
            url=data['url'],
            period=data.get('period', 'weekly'),
            range_val=data.get('range', '1 year'),
            ma_config=ma_config_json
        )
        db.session.add(preset)
        db.session.commit()
        return jsonify({'success': True, 'id': preset.id})
    else:
        # GET
        presets = ScanPreset.query.filter_by(user_id=current_user.id).all()
        result = []
        for p in presets:
            ma_data = None
            if p.ma_config:
                try:
                    ma_data = json.loads(p.ma_config)
                except:
                    pass
            
            result.append({
                'id': p.id,
                'title': p.title,
                'description': p.description,
                'url': p.url,
                'period': p.period,
                'range': p.range_val,
                'moving_averages': ma_data
            })
        return jsonify(result)

@app.route('/api/presets/<int:id>', methods=['DELETE'])
@login_required
def delete_preset(id):
    preset = ScanPreset.query.get_or_404(id)
    if preset.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    db.session.delete(preset)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/start_generation', methods=['POST'])
@login_required
def start_generation():
    data = request.json
    # Can accept raw URL or preset ID
    screener_url = data.get('url')
    period = data.get('period', 'weekly')
    s_range = data.get('range', '1 year')
    moving_averages = data.get('moving_averages') # New
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'status': 'queued', 
        'processed': 0, 
        'total': 0, 
        'current_company': '',
        'telegram_sent': False
    }

    user_config = {
        'tg_token': current_user.telegram_bot_token,
        'tg_chat_id': current_user.telegram_chat_id
    }

    thread = threading.Thread(target=process_job, args=(job_id, screener_url, period, s_range, moving_averages, user_config))
    thread.daemon = True
    thread.start()
    
    return jsonify({'job_id': job_id})

@app.route('/status/<job_id>', methods=['GET'])
def check_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'status': 'not_found'}), 404
    
    response = {
        'status': job['status'],
        'processed': job.get('processed', 0),
        'total': job.get('total', 0),
        'current_company': job.get('current_company', ''),
        'error': job.get('error'),
        'telegram_sent': job.get('telegram_sent')
    }
    return jsonify(response)

@app.route('/download/<job_id>', methods=['GET'])
def download(job_id):
    job = jobs.get(job_id)
    if not job or job['status'] != 'completed' or not job['result']:
         return jsonify({'error': 'File not ready or job failed'}), 400
    
    pdf_buffer = BytesIO(job['result'])
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mimetype='application/pdf'
    )

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Use 0.0.0.0 for external access
    app.run(host='0.0.0.0', debug=True, port=5000)
