FROM python:3.10-slim

WORKDIR /app

# PyNaClなどのC拡張ライブラリに必要な依存関係をインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# エントリポイントを api/index.py の app に指定
CMD ["uvicorn", "api.index:app", "--host", "0.0.0.0", "--port", "8080"]
