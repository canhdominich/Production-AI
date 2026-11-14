FROM python:3.12-slim AS runtime
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /srv
COPY project-platform/deploy/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt
COPY platform /srv/platform
COPY data /srv/data
COPY project-platform/solution/anhti_platform /srv/app/anhti_platform
ENV PYTHONPATH=/srv/app PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ANHTI_PLATFORM_DIR=/srv/platform ANHTI_DATA_DIR=/srv/data
USER app
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=10 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"]
CMD ["uvicorn", "anhti_platform.api:build_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8000"]
