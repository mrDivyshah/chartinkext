import threading
import uuid
from flask import Flask, render_template, request, send_file, jsonify, after_this_request

# ... imports ... same as before
import os
import json
import time
import base64
import requests
from io import BytesIO
from datetime import datetime
from PIL import Image as PILImage
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)
jobs = {}

def web_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--verbose")
    options.add_argument('--no-sandbox')
    # options.add_argument('--headless') # Disabled for debugging
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # Automatically enable headless in Docker/Production
    if os.path.exists('/.dockerenv') or os.environ.get('HEADLESS', 'false').lower() == 'true':
        options.add_argument('--headless=new') # Use new headless mode
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--disable-extensions')
        # options.binary_location = "/usr/bin/google-chrome" # Let Selenium find it in PATH
        print("Running in Headless mode (Docker/Env detected)")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"Error setting up driver: {e}")
        raise e

def get_url_and_index(driver):
    results = []
    index = 1
    while True:
        try:
            # Wait for the Stock results to load by checking for the header
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Stock Name')]"))
            )
            time.sleep(2) # Allow render to settle

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Find all links that point to fundamentals (F.A links)
            # The structure is usually class="text-teal-700" or similar, but href is reliable
            links = soup.find_all('a', href=True)
            page_links = []
            for link in links:
                href = link.get('href')
                if 'fundamentals' in href:
                    href = href.replace('fundamentals', 'stocks')
                    full_link = f"https://chartink.com{href}"
                    # Avoid duplicates
                    if full_link not in results and full_link not in page_links:
                         page_links.append(full_link)
            
            if not page_links:
                print("No links found on this page.")
                break
                
            results.extend(page_links)
            print(f"Found {len(page_links)} links on this page. Total: {len(results)}")

            # Pagination handling
            try:
                # Try finding the Next button. DataTables usually has an ID or class.
                next_button = driver.find_elements(By.XPATH, "//a[contains(text(), 'Next')]")
                if not next_button:
                     next_button = driver.find_elements(By.ID, 'DataTables_Table_0_next')
                
                if next_button:
                    btn = next_button[0]
                    classes = btn.get_attribute('class')
                    if 'disabled' in classes:
                        print("Next button disabled. End of pages.")
                        break
                    
                    driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(3) # Wait for next page load
                else:
                    print("Next button not found. Assuming single page.")
                    break
            except Exception as e:
                print(f"Pagination error: {e}")
                break
                
        except Exception as e:
            print("No more pages or an error occurred:", e)
            import traceback
            traceback.print_exc()
            try:
                driver.save_screenshot('error_scraping_urls.png')
            except:
                pass
            break

    return results

def get_image_from_link(driver, url, timeframe, s_range, form_data, retries=3):
    driver.get(url)
    time.sleep(2)
    try:
        form_data_json = json.dumps(form_data)
        
        form_js_template = """
        const formData = {form_data};

        function fillForm(formId, data) {{
            const form = document.getElementById(formId);
            if (!form) {{
                console.error("Form not found");
                return;
            }}

            Object.keys(data).forEach(key => {{
                const field = form.querySelector(`[name="${{key}}"]`);
                const fieldData = data[key];

                if (field) {{
                    if (fieldData.type === "checkbox") {{
                        field.checked = fieldData.value;
                    }} else if (fieldData.type === "text") {{
                        field.value = fieldData.value;
                    }} else if (fieldData.type === "select") {{
                        field.value = fieldData.value;
                    }}
                }}
            }});
        }}
        fillForm("newone3", formData);
        """
        form_js = form_js_template.format(form_data=form_data_json)
        driver.execute_script(form_js)

        timeframe_mapping = {
            "1 day": "1", "2 days": "2", "3 days": "3", "5 days": "5", "10 days": "10",
            "1 month": "22", "2 months": "44", "3 months": "66", "4 months": "91",
            "6 months": "121", "9 months": "198", "1 year": "252", "2 years": "504",
            "3 years": "756", "5 years": "1008", "8 years": "1764", "All Data": "5000"
        }
        
        range_mapping = {
            "Daily": "d", "Weekly": "w", "Monthly": "m", "1 Minute": "1_minute",
            "2 Minute": "2_minute", "3 Minute": "3_minute", "5 Minute": "5_minute",
            "10 Minute": "10_minute", "15 Minute": "15_minute", "20 Minute": "20_minute",
            "25 Minute": "25_minute", "30 Minute": "30_minute", "45 Minute": "45_minute",
            "75 Minute": "75_minute", "125 Minute": "125_minute", "1 hour": "60_minute",
            "2 hour": "120_minute", "3 hour": "180_minute", "4 hour": "240_minute"
        }

        try:
            Select(driver.find_element(By.ID, "ti")).select_by_value(timeframe_mapping.get(timeframe, "252"))
            Select(driver.find_element(By.ID, "d")).select_by_value(range_mapping.get(s_range, "w"))
        except Exception as e:
            print(f"Error setting selects: {e}")

        driver.find_element(By.ID, "innerb").click()
        
        try:
            iframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "ChartImage"))
            )
            driver.switch_to.frame(iframe)
        except TimeoutException:
            print("Chart iframe not found")
            return None, None

        for attempt in range(retries):
            try:
                body_html = driver.execute_script("return document.body.innerHTML;")
                if not body_html:
                    raise ValueError("innerHTML is empty")
                
                soup = BeautifulSoup(body_html, "html.parser")
                img_tag = soup.find("img", {"id": "cross"})
                
                if img_tag:
                    company_name_elem = driver.execute_script("return window.parent.document.querySelector(\"h3[style='margin: 0px;margin-left: 5px;font-size:20px']\").innerText")
                    company_name = company_name_elem if company_name_elem else "Unknown"
                    
                    img_data_base64 = img_tag["src"].split(",")[1]
                    return company_name, img_data_base64
            except Exception as e:
                time.sleep(2)
        
        return None, None

    except Exception as e:
        print(f"Error getting image for {url}: {e}")
        return None, None

def generate_pdf(data):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    a4_width, a4_height = A4
    page_height = a4_height

    for item in data:
        company_name = item['company_name']
        image = item['image']
        
        page_width = a4_width
        img_width, img_height = image.size
        aspect_ratio = img_height / img_width
        
        scaled_width = page_width - 40 
        scaled_height = scaled_width * aspect_ratio
        
        if scaled_height > (page_height - 100):
            scaled_height = page_height - 100
            scaled_width = scaled_height / aspect_ratio

        img_buffer = BytesIO()
        image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        x = (page_width - scaled_width) / 2
        y = (page_height - scaled_height) / 2 
        
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(page_width / 2, page_height - 50, company_name)
        
        c.drawImage(ImageReader(img_buffer), x, y, width=scaled_width, height=scaled_height)
        c.showPage()

    c.save()
    return buffer.getvalue()

def process_job(job_id, screener_url, period, s_range, form_data):
    jobs[job_id]['status'] = 'running'
    driver = None
    try:
        driver = web_driver()
        driver.get(screener_url)
        
        jobs[job_id]['status'] = 'scraping_urls'
        results = get_url_and_index(driver)
        
        jobs[job_id]['total'] = len(results)
        jobs[job_id]['status'] = 'fetching_charts'
        
        processed_data = []
        for i, url in enumerate(results):
            if jobs[job_id].get('canceled'):
                break
                
            company_name, img_data_base64 = get_image_from_link(driver, url, period, s_range, form_data)
            if company_name and img_data_base64:
                img_data = base64.b64decode(img_data_base64)
                image = PILImage.open(BytesIO(img_data))
                processed_data.append({"company_name": company_name, "image": image})
            
            jobs[job_id]['processed'] = i + 1
            jobs[job_id]['current_company'] = company_name if company_name else url

        if not processed_data:
             jobs[job_id]['status'] = 'failed'
             jobs[job_id]['error'] = 'No data found or charts could not be generated.'
             return

        jobs[job_id]['status'] = 'generating_pdf'
        pdf_bytes = generate_pdf(processed_data)
        jobs[job_id]['result'] = pdf_bytes
        jobs[job_id]['status'] = 'completed'

    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)
    finally:
        if driver:
            driver.quit()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start_generation', methods=['POST'])
def start_generation():
    data = request.json
    screener_url = data.get('screener_url')
    period = data.get('period')
    s_range = data.get('range')
    moving_avg_data = data.get('moving_averages')
    
    form_data = {}
    select_map = {"open": "o", "High": "h", "Low": "l", "Close": "c"}
    type_map = {"Simple": "SMA", "Exponential": "EMA", "Weighted": "WMA", "Triangular": "TMA"}
    
    for i, ma in enumerate(moving_avg_data):
        idx = i + 1
        form_data[f"a{idx}"] = {"type": "checkbox", "value": ma['enabled']}
        if ma['enabled']:
            form_data[f"a{idx}t"] = {"type": "select", "value": select_map.get(ma['select'], 'c')}
            form_data[f"a{idx}v"] = {"type": "select", "value": type_map.get(ma['type'], 'SMA')}
            form_data[f"a{idx}l"] = {"type": "text", "value": str(ma['number'])}

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'status': 'initializing',
        'total': 0,
        'processed': 0,
        'current_company': '',
        'error': None,
        'result': None
    }
    
    thread = threading.Thread(target=process_job, args=(job_id, screener_url, period, s_range, form_data))
    thread.daemon = True
    thread.start()
    
    return jsonify({'job_id': job_id})

@app.route('/status/<job_id>', methods=['GET'])
def check_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    # Don't send the result binary data in status check
    response = {
        'status': job['status'],
        'total': job['total'],
        'processed': job['processed'],
        'current_company': job.get('current_company', ''),
        'error': job.get('error')
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
