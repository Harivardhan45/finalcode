FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y graphviz && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r UI-main/backend/requirements.txt

# Expose port
EXPOSE 8000

# Start the backend (with your scripts)
CMD python UI-main/backend/auto_hlsd.py && \
    python UI-main/backend/update_confluence_hlsd.py && \
    uvicorn UI-main/backend/main:app --host 0.0.0.0 --port 8000 