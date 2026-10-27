FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Create outputs directory
RUN mkdir -p outputs

# Expose the port Render will use
EXPOSE 10000

# Run with uvicorn in production mode
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
