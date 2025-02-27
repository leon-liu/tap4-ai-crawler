# Stage 1: Builder stage
FROM python:3.10 AS builder

# 1.1 复制必要文件
WORKDIR /app
COPY requirements.txt /app/
COPY weiruanyahei.ttf /app/
COPY util/* /app/util/
COPY .env /app/
COPY *.py /app/

# 1.2 安装python依赖
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
RUN pip install --target=/app/dependencies -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies and Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libxss1 \
    libudev1 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxtst6 \
    fonts-liberation \
    chromium \
    chromium-driver \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Copy font file and dependencies from builder stage
WORKDIR /usr/share/fonts/chinese/
COPY --from=builder /app/weiruanyahei.ttf /usr/share/fonts/chinese/
RUN fc-cache -f -v

# Copy application files from builder stage
COPY --from=builder /app/dependencies /app/dependencies
COPY --from=builder /app/util/* /app/util/
COPY --from=builder /app/.env /app/
COPY --from=builder /app/*.py /app/

# Install additional Python packages
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir playwright uvicorn && \
    playwright install chromium && \
    playwright install-deps

WORKDIR /app

# Create logs directory and set permissions
RUN mkdir -p /app/logs && \
    chmod +x /app/main*.py

# Set environment variables
ENV PYTHONPATH=/app/dependencies
ENV DISPLAY=:99
ENV PLAYWRIGHT_CHROMIUM_PATH=/usr/bin/chromium

# Expose port
EXPOSE 8040

# Start Xvfb and application
CMD Xvfb :99 -screen 0 1024x768x16 & uvicorn main_api:app --host 0.0.0.0 --port 8040 --workers 4