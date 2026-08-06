FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default command runs the API; docker-compose overrides this for the worker service.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
