FROM python:3.11-slim

ENV PYTHONUNBUFFERED=True
WORKDIR /app

# Копируем и устанавливаем зависимости
COPY requirements.txt .
# Pip сам установит правильные версии из requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

EXPOSE 8080

# Запускаем
CMD ["python", "main_webhook.py"]

