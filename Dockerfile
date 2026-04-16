FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Session logs are written here at runtime — declare as a volume
# so study data persists even after the container stops
RUN mkdir -p session_logs
VOLUME ["/app/session_logs"]

EXPOSE 7860

#   docker run --env-file .env -p 7860:7860 -v $(pwd)/session_logs:/app/session_logs metamodeling-ui
CMD ["python", "app.py"]
