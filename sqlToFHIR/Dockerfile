
FROM python:3.8-slim

WORKDIR /app
COPY sqlToFHIR.py sqlToFHIR.py
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir pyyaml
RUN pip install --no-cache-dir --upgrade pip && \
    pip install -r requirements.txt
#ENTRYPOINT ["python3"]
ENV PYTHONUNBUFFERED=1
CMD ["python3", "./sqlToFHIR.py"]

