FROM python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TOMESHED_DB=/data/tomeshed.db TOMESHED_LIBRARY_DIR=/library HOST=0.0.0.0 PORT=5000
RUN groupadd --gid 10001 tomeshed && useradd --uid 10001 --gid tomeshed --create-home tomeshed && install -d -o tomeshed -g tomeshed /data /library
WORKDIR /app
COPY requirements-container.txt ./
RUN pip install --no-cache-dir --no-compile --require-hashes -r requirements-container.txt
COPY tomeshed.py document_library.py document_processing.py reader_service.py preview_service.py organization_service.py bookshelf_service.py file_workflows.py healthcheck.py VERSION ./
COPY templates/ templates/
COPY static/ static/
VOLUME ["/data", "/library"]
EXPOSE 5000
USER 10001:10001
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python /app/healthcheck.py
CMD ["python", "tomeshed.py"]
