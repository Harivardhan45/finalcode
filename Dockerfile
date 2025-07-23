# Use an official Python image
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y graphviz

# Set workdir
WORKDIR /app

# Copy your code
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r UI-main/backend/requirements.txt

# Expose the port
EXPOSE 8000

# Start the app
CMD ["uvicorn", "UI-main/backend/main:app", "--host", "0.0.0.0", "--port", "8000"] 