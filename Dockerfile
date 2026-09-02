FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Chromium headless para core/claude_slide_renderer.py (composición de
# carruseles vía Claude + Playwright). --with-deps instala también las
# librerías de sistema que Chromium necesita (fontconfig, libnss3, etc.).
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
