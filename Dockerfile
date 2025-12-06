# Basisimage
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY dailyRunner.sh .
COPY todo.py .
COPY .env .
CMD ["sh", "/app/dailyRunner.sh"]
