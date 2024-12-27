# Use the official Python image from the Docker Hub
FROM python:3.11-slim

# Prevents Python from writing pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1

# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg mediainfo && \
    rm -rf /var/lib/apt/lists/*

# Create a directory for the app
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port (optional, for documentation)
EXPOSE 8080

# Define the command to run the application using the PORT environment variable
CMD ["sh", "-c", "uvicorn api.webhook:app --host 0.0.0.0 --port $PORT"]