FROM python:3.11-slim

WORKDIR /app

# libpq is needed by psycopg[binary] at runtime on slim images in some cases;
# installed explicitly rather than relying on the wheel bundling everything.
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# FR-109: the deploy command (ADR-002) passes --build-arg FILMRUNNER_GIT_SHA
# so /healthz can report which commit is actually serving traffic. Left empty
# for a plain `docker build`/local dev; /healthz omits the field entirely then.
ARG FILMRUNNER_GIT_SHA=""
ENV FILMRUNNER_GIT_SHA=$FILMRUNNER_GIT_SHA

EXPOSE 8000
# No access log: personal tokens are in URL paths. app/request_log.py logs the route template instead.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
