# Use a Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV PORT 8080

# Create and set the working directory
WORKDIR /app

# Copy the requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . /app/

# Expose the port FastAPI will run on
EXPOSE 8080

# Run the app using Uvicorn
CMD ["uvicorn", "main:app", "--host=0.0.0.0", "--port=8080"]
