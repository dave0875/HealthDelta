FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY healthdelta ./healthdelta
COPY deploy/fixtures/profile_export ./deploy/fixtures/profile_export

ARG HEALTHDELTA_VERSION=0.0.0+container
ARG HEALTHDELTA_GIT_SHA=unknown
ENV HEALTHDELTA_VERSION="${HEALTHDELTA_VERSION}"
ENV HEALTHDELTA_GIT_SHA="${HEALTHDELTA_GIT_SHA}"

RUN python -m pip install --upgrade pip \
    && SETUPTOOLS_SCM_PRETEND_VERSION="${HEALTHDELTA_VERSION}" python -m pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "healthdelta.backend_server"]
