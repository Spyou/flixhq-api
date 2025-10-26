FROM python:3.11-slim

# Install Chrome and dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    ca-certificates \
    && wget -q https://dl.google.com/linux/linux_signing_key.pub -O /tmp/google.pub \
    && gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg /tmp/google.pub \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* /tmp/google.pub

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Expose port (Railway uses dynamic PORT)
EXPOSE 8080

# Run the app
CMD gunicorn flixhq_api:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1
