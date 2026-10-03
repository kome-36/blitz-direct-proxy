FROM python:3.11-slim
WORKDIR /app
COPY entrypoint.py ./
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
 && mkdir -p /app/bin \
 && curl -fsSL -o /tmp/xray.zip https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip \
 && python3 -c "import zipfile; zipfile.ZipFile('/tmp/xray.zip').extractall('/app/bin')" \
 && chmod +x /app/bin/xray && rm -f /tmp/xray.zip \
 && apt-get purge -y curl && apt-get autoremove -y -qq && rm -rf /var/lib/apt/lists/*
EXPOSE 8080
CMD ["python3", "/app/entrypoint.py"]
