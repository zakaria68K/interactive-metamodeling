FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p session_logs user_profiles study_data
VOLUME ["/app/session_logs", "/app/user_profiles", "/app/study_data"]

EXPOSE 7860

CMD ["python", "app.py"]
