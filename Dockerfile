# Используем официальный Python образ
FROM python:3.9-slim

# Устанавливаем зависимости для проекта
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код в контейнер
COPY . /app

# Устанавливаем переменные окружения
ENV WEBAPP_HOST=0.0.0.0
ENV WEBAPP_PORT=8888

# Указываем команду для запуска приложения
CMD ["python", "main.py"]
