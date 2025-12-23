# How to Run the Chartink PDF Generator Flask App

This Flask application converts your Chartink screener results into a PDF with charts.

## Prerequisites

1.  **Python 3.10+**: Ensure Python is installed and added to your `PATH`.
2.  **Chrome Browser**: The app uses Selenium with Chrome. Ensure you have Google Chrome installed.

## Installation

1.  Open a terminal (Command Prompt or PowerShell).
2.  Navigate to the `flask_app` directory:
    ```cmd
    cd "d:\shellGPT\chartink project\flask_app"
    ```
3.  Install the required dependencies:
    ```cmd
    pip install -r requirements.txt
    ```

## Running the App

1.  Start the Flask server:
    ```cmd
    python app.py
    ```
2.  You should see output indicating the server is running (e.g., `Running on http://127.0.0.1:5000`).
3.  Open your web browser and go to:
    `http://127.0.0.1:5000`

## Usage

1.  Enter the **Chartink Screener URL**.
2.  Select the **Range** and **Period**.
3.  Optionally enable **Moving Averages** and configure them.
4.  Click **Generate PDF**.
5.  Wait for the process to complete (it scans the screener and fetches charts for each stock). This may take a minute or two depending on the number of stocks.
6.  The PDF will automatically download when ready.

## TroubleShooting

-   **Chrome Driver Error**: If you see errors related to Chrome Driver, `webdriver-manager` should handle it automatically. Try running `pip install --upgrade webdriver-manager`.
-   **Connection Refused**: Ensure no other service is using port 5000. You can change the port in `app.py` at the bottom (`port=5000`).
