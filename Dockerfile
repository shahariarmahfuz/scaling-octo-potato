# Base image using Python 3.10 slim version
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install ffmpeg and cleanup apt cache
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app.py .

# Create directory for HLS output
RUN mkdir hls_output

# Expose the port the HTTP server will run on
EXPOSE 8000

# Command to run the application
# Expects the YouTube URL as a command-line argument
CMD ["python", "app.py"]
