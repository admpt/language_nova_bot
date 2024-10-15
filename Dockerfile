# Указываем базовый образ Python
FROM python:3.12

# Устанавливаем рабочую директорию
WORKDIR /english_bot

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все остальные файлы проекта
COPY . .

# Указываем команду для запуска приложения
CMD ["python", "main.py"]
# Измени на нужный файл, если нужно