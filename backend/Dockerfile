# Start from the official Python 3.10 slim image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# This is the FIXED command with "apt-get update"
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc g++ \
    curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# We copy requirements.txt first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code
COPY . .

# Expose the port Gunicorn will run on
EXPOSE 5000

# Run the application
CMD ["gunicorn", "-k", "eventlet", "--bind", "0.0.0.0:5000", "run:app"]