# Use Python 3.9 slim as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the app code into the container
COPY . /app

# Expose port 8080 for the Cloud Run service
EXPOSE 8080

# Run the Flask app
CMD ["python", "app.py"]
