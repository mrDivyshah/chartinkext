FROM python:3.10-slim

# Install system dependencies, including Chrome and its deps
# Install system dependencies (wget, gnupg, unzip, curl)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    libnss3 \
    libfontconfig1 \
    fonts-liberation \
    libasound2 \
    xdg-utils \
    libgbm1 \
    libgtk-3-0 \
    --no-install-recommends

# Install Google Chrome Stable directly from the .deb file
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Explicitly install gunicorn for production serving
RUN pip install gunicorn

# Copy app code
COPY . .

# Environment variables
ENV PORT=5000
ENV FLASK_APP=app.py

# Expose the port
EXPOSE 5000

# Run the application with Gunicorn
CMD gunicorn --bind 0.0.0.0:$PORT app:app --timeout 120
