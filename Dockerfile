FROM python:3.15.0-slim@sha256:f5b92f2a669a4c347044f29367f31983280b648250ca94dea66f98c53bc87e58
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
