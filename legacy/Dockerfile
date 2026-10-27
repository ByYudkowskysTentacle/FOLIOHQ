FROM python:3.12-slim
RUN useradd --create-home --uid 10001 chq
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir . && mkdir -p /app/data /app/out && chown -R chq /app
USER chq
VOLUME ["/app/data", "/app/out"]
ENTRYPOINT ["folio-chq", "-c", "/app/config.yaml"]
CMD ["run"]
