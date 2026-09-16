FROM python:3.12-slim-bullseye

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy the application into the container.
COPY . /app

# Install the application dependencies.
# The lock is used when it matches pyproject.toml. `--frozen` is deliberately
# not used: some networks cannot reach every pythonhosted CDN path, so the lock
# cannot always be regenerated locally, and the build resolves from
# pyproject.toml constraints instead of failing outright.
WORKDIR /app
RUN uv sync --no-cache

# Run the application.
CMD /app/.venv/bin/fastapi run app/main.py --port ${PORT:-8000}
