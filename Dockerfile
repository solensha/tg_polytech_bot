FROM python:3.11-slim

# Устанавливаем Node.js и pm2
RUN apt-get update && \
    apt-get install -y curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g pm2

# Установка supervisord для управления процессами
RUN apt-get install -y supervisor

# Рабочая директория
WORKDIR /app

# Копируем все файлы
COPY . /app

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r Bot/requirements.txt
RUN pip install --no-cache-dir -r Parser/requirements.txt

# Копируем конфиг
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Запуск supervisord
CMD ["/usr/bin/supervisord"]
