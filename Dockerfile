# SelfDeploy — single-container self-deploy (local-first)
# The CEO's data never leaves this container unless --llm is explicitly used.
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY selfdeploy ./selfdeploy
RUN pip install --no-cache-dir . cryptography

# Local-only UI. Publish with: docker run -p 127.0.0.1:8787:8787 selfdeploy
EXPOSE 8787
ENTRYPOINT ["selfdeploy"]
CMD ["serve", "--port", "8787"]
