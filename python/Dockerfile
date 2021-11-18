
FROM python:3.8-slim

WORKDIR /app
COPY fhirToS3.py fhirToS3.py
COPY requirements.txt requirements.txt
COPY curlCommands.py curlCommands.py
COPY noklus_patient_observation_template.xml noklus_patient_observation_template.xml
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir pyyaml
RUN pip install --no-cache-dir --upgrade pip && \
    pip install -r requirements.txt
#ENTRYPOINT ["python3"]
ENV PYTHONUNBUFFERED=1
CMD ["python3", "./fhirToS3.py"]

