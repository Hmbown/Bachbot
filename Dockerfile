FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY bachbot /app/bachbot
COPY data /app/data
COPY examples /app/examples

RUN python -m pip install --upgrade pip && python -m pip install .

EXPOSE 8000

CMD ["bachbot", "serve", "--host", "0.0.0.0", "--port", "8000"]
