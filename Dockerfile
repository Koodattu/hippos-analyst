# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
WORKDIR /app
COPY LICENSE /app/LICENSE
RUN install -d -o 10001 -g 10001 /data && test -r /usr/share/zoneinfo/Europe/Helsinki

FROM scratch AS lib-amd64
ADD --checksum=sha256:de32f8e147ee8f969599a00b7145e8561b943e916b0132b811037f8f71952a0e https://github.com/catboost/catboost/releases/download/v1.2.10/libcatboostmodel-linux-x86_64-1.2.10.so /libcatboostmodel.so

FROM scratch AS lib-arm64
ADD --checksum=sha256:d1b5d12f57ef72fd43505d9fbc1ea30d93d54ef0f305484c6bbfde8642e99a5b https://github.com/catboost/catboost/releases/download/v1.2.10/libcatboostmodel-linux-aarch64-1.2.10.so /libcatboostmodel.so

FROM lib-${TARGETARCH} AS model-library

FROM base AS predictor
COPY --from=model-library --chmod=0444 /libcatboostmodel.so /opt/libcatboostmodel.so
ENV HIPPOS_CATBOOST_LIBRARY=/opt/libcatboostmodel.so
COPY hippos_analyst ./hippos_analyst
USER 10001:10001

FROM base AS runtime
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --only-binary=:all: gunicorn==27.0.1 packaging==26.2
COPY hippos_analyst ./hippos_analyst
USER 10001:10001
EXPOSE 8765
CMD ["gunicorn", "--preload", "--no-control-socket", "--bind=0.0.0.0:8765", "--workers=1", "--threads=2", "--timeout=90", "hippos_analyst.server:deployment_app()"]
