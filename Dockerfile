FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.12-slim-bookworm

WORKDIR /bot

RUN mkdir -p /bot/db && \
	apt-get update && \
	apt-get install -y --no-install-recommends ffmpeg && \
	apt-get clean && \
	rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local

ENV PATH="/root/.local/bin:$PATH"

COPY . .
RUN rm -rf venv __pycache__

CMD ["python", "bot.py"]