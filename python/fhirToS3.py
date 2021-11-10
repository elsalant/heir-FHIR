''' Copies FHIR resource in JSON from Kafka queue to S3 bucket.  The bucket name will
correspond to the resource name.
No buffering of resources is done on the write - this can be achieved by configuring Kafka for batching'''
import json
import boto3
import tempfile

import uuid
import os

import pandas as pd
import yaml
from kafka import KafkaConsumer
from json import loads
from kubernetes import client, config
import base64

from curlCommands import handleQuery

TEST = True

DEFAULT_KAFKA_TOPIC = 'fhir-wp2'
DEFAULT_KAKFA_HOST = 'kafka.fybrik-system:9092'
if TEST:
    DEFAULT_FHIR_HOST = 'https://localhost:9443'
else:
    DEFAULT_FHIR_HOST = 'ibmfhir.fybrik-system:9443'
DEFAULT_FHIR_USER = 'fhiruser'
DEFAULT_FHIR_PW = 'change-password'

PATIENT_LOOKUP = '/fhir-server/api/v4/Observation'
BUCKET_PREFIX = '-heir-'

TEST_BUNDLE_DATA = '{ \
  "resourceType": "Bundle", \
  "id": "bundle-example", \
  "meta": { \
    "lastUpdated": "2014-08-18T01:43:30Z" \
  }, \
  "type": "searchset", \
  "total": 3,  \
  "entry": [  \
    {  \
      "fullUrl": "https://example.com/base/MedicationRequest/3123",  \
      "resource": {   \
        "resourceType": "MedicationRequest",  \
        "id": "3123",  \
        "text": {   \
          "status": "generated"  \
         },  \
        "status": "unknown",  \
        "intent": "order",  \
        "medicationReference": {  \
          "reference": "Medication/example"  \
        },  \
        "subject": {  \
          "reference": "Patient/347"  \
        }  \
      },  \
      "search": {  \
        "mode": "match",  \
        "score": 1  \
      }  \
    },  \
    {  \
      "fullUrl": "https://example.com/base/Medication/example",  \
      "resource": {  \
        "resourceType": "Medication",  \
        "id": "example",  \
        "text": {   \
          "status": "generated"  \
        }  \
      },  \
      "search": {  \
        "mode": "include"  \
      }  \
    }  \
  ]  \
}'

TEST_PATIENT = '{ \
  "resourceType": "Patient", \
  "id" : "005",  \
    "name": [   \
    {   \
      "family": "Simpson",   \
      "given": [   \
        "Homer"  \
      ]    \
    }    \
  ]   \
}'

TEST_OBSERVATION = '{ \
  "resourceType": "Observation", \
  "id": "f001",  \
  "identifier": [  \
    {  \
      "use": "official",  \
      "system": "http://www.bmc.nl/zorgportal/identifiers/observations",  \
      "value": "6323"  \
    }  \
  ],  \
  "status": "final",  \
  "code": {  \
    "coding": [  \
      {  \
        "system": "http://loinc.org",  \
        "code": "15074-8",  \
        "display": "Glucose [Moles/volume] in Blood"  \
      }  \
    ]  \
  },  \
  "subject": {  \
    "reference": "Patient/f001",  \
    "display": "P. van de Heuvel"  \
  },  \
  "effectivePeriod": {  \
    "start": "2013-04-02T09:30:10+01:00"  \
  },  \
  "issued": "2013-04-03T15:30:10+01:00",  \
  "performer": [  \
    {  \
      "reference": "Practitioner/f005",  \
      "display": "A. Langeveld"  \
    }  \
  ],  \
  "valueQuantity": {  \
    "value": 6.3,  \
    "unit": "mmol/l",  \
    "system": "http://unitsofmeasure.org",  \
    "code": "mmol/L"  \
  }  \
}'


def get_resource_buckets(searchPrefix):
    # Get a bucket with a name that contains the passed prefix
    bucketCollection = connection.buckets.all()
    bucketList = []
    for bucket in bucketCollection:
        bucketList.append(str(bucket.name))
    matchingBuckets = [s for s in bucketList if searchPrefix in s]
    if (matchingBuckets):
        print("matchingBuckets = " + str(matchingBuckets))
    return matchingBuckets

def connect_to_kafka():
    if TEST:
        return
    consumer = None
    try:
        consumer = KafkaConsumer(
            kafka_topic,
            bootstrap_servers=[kafka_host],
            group_id=kafka_topic,
            auto_offset_reset='latest',
            enable_auto_commit=True,
            value_deserializer=lambda x: loads(x.decode('utf-8')))
    except:
        raise Exception("Kafka did not connect for host " + kafka_host + " and  topic " + kafka_topic)

    print("Connection to kafka at host " + kafka_host + " and  topic " + kafka_topic + " succeeded!")
    return consumer

def create_bucket(bucket_prefix, s3_connection):
    session = boto3.session.Session()
    current_region = session.region_name
    if current_region == None:
        current_region = ''
    bucket_name = create_bucket_name(bucket_prefix)
    bucket_response = s3_connection.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={
        'LocationConstraint': current_region})
    print(bucket_name, current_region)
    return bucket_name, bucket_response

def create_bucket_name(bucket_prefix):
    # The generated bucket name must be between 3 and 63 chars long
    return ''.join([bucket_prefix, str(uuid.uuid4())])

def contentToFile(content, fnameSeed):
    random_file_name = ''.join([str(uuid.uuid4().hex[:6]), fnameSeed])
    try:
        writeLine = str(content)
        tempFile = tempfile.NamedTemporaryFile(prefix=random_file_name, suffix=".csv", mode='w+t' )
        print("Created file is:", tempFile.name)
        tempFile.write(writeLine)
        tempFile.seek(0)   # Rewind - is this necessary?
    except:
        tempFile.close()
        raise IOError("error writing content to temp file")
    return tempFile

def write_to_bucket(bucketName, tempFile, fnameSeed):
    try:
        bucketObject = connection.Object(bucket_name=bucketName, key=fnameSeed)
        print("about to write to S3: bucketName = " + bucketName + " fnameSeed = " + fnameSeed)
        bucketObject.upload_file(tempFile.name)
    finally:
        tempFile.close()

def getSecretKeys(secret_name, secret_namespace):
    try:
        config.load_incluster_config()  # in cluster
    except:
        config.load_kube_config()   # useful for testing outside of k8s
    v1 = client.CoreV1Api()
    secret = v1.read_namespaced_secret(secret_name, secret_namespace)
    accessKeyID = base64.b64decode(secret.data['access_key_id'])
    secretAccessKey = base64.b64decode(secret.data['secret_access_key'])
    return(accessKeyID.decode('ascii'), secretAccessKey.decode('ascii'))

def main():
    global connection
    global kafka_topic
    global kafka_host
    global fhir_host
    global fhir_pw
    global fhir_user

    print("starting module!!")

    CM_PATH = '/etc/conf/conf.yaml'
    cmDict = []

    kafka_host = os.getenv("HEIR_KAFKA_HOST") if os.getenv("HEIR_KAFKA_HOST") else DEFAULT_KAKFA_HOST
    fhir_host = os.getenv("HEIR_FHIR_HOST") if os.getenv("HEIR_FHIR_HOST") else DEFAULT_FHIR_HOST
    fhir_user = os.getenv("HEIR_FHIR_USER") if os.getenv("HEIR_FHIR_USER") else DEFAULT_FHIR_USER
    fhir_pw = os.getenv("HEIR_FHIR_PW") if os.getenv("HEIR_FHIR_PW") else DEFAULT_FHIR_PW

    try:
        with open(CM_PATH, 'r') as stream:
            cmReturn = yaml.safe_load(stream)
        print('cmReturn = ', cmReturn)
        cmDict = cmReturn.get('data', [])

        s3_URL = cmDict['S3_URL']

        secret_namespace = cmDict['SECRET_NSPACE']
        secret_fname = cmDict['SECRET_FNAME']

        print("secret_namespace = " + secret_namespace + ", secret_fname = " + secret_fname)
        s3_access_key, s3_secret_key = getSecretKeys(secret_fname, secret_namespace)
        print("access key found: " + s3_access_key + "secret_key found: " + s3_secret_key)

        print("s3_URL = ", str(s3_URL))

        assert s3_access_key != '', 'No s3_access key found!'
        assert s3_secret_key != '', 'No s3_secret_key found!'

        connection = boto3.resource(
            's3',
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key,
            endpoint_url=s3_URL
        )
    except:
        print("no file found " + CM_PATH)
    try:
        kafka_topic = cmDict['WP2_TOPIC']
        print('kafka_topic passed as ' + kafka_topic)
    except:
        kafka_topic = DEFAULT_KAFKA_TOPIC
        print('using DEFAULT_KAFKA_TOPIC = ' + DEFAULT_KAFKA_TOPIC)
    try:
        kafka_host = cmDict['HEIR_KAFKA_HOST']
        print('kafka_host passed as ' + kafka_host)
    except:
        kafka_host = DEFAULT_KAKFA_HOST
        print('using DEFAULT_KAFKA_HOST = ' + DEFAULT_KAKFA_HOST)

    if TEST:
        consumer = [TEST_OBSERVATION]
    else:
        consumer = connect_to_kafka()
    unique_id_list = read_from_kafka(consumer)
    policyJson = get_policy()

    for id in unique_id_list:
        df = read_from_fhir(id)
        redacted_df = apply_policy(df,policyJson)
        write_to_S3(redacted_df, "Observation")
    if not TEST:
        consumer.close()

def read_from_fhir(id):
    print("querying FHIR server for patient_id "+id)
    queryURL = fhir_host
    queryString = PATIENT_LOOKUP
    params = {'subject': id}
    auth = (fhir_user, fhir_pw)

    observationRecord = handleQuery(queryURL, queryString, auth, params, 'GET')
    observationDF = pd.DataFrame.from_dict(observationRecord[0])
    return observationDF

def get_policy():
    if TEST:
        policies = '[{"name": "Redact PII columns", "action": "RedactColumn", "columns": ["id"]}]'
    return(json.loads(policies))

def apply_policy(df, policies):
    redactedData = []
    # Redact df based on policy returned from the policy manager
    for policy in policies:
        action = policy['action']
        if action == 'RedactColumn':
            for col in policy['columns']:
                df.drop(policy[col], inplace=True, axis=1)
            redactedData.append(df.to_json())
        if action == 'AverageColumn':
            for col in policy['columns']:
                mean = df[col].mean()
                meanStr = '{\"'+col+'\": \"'+ mean+'\"}'
                redactedData.append(meanStr)
        if action == 'StdDev':
            for col in policy['columns']:
                mean = df[col].mean()
                meanStr = '{\"' + col + '\": \"' + mean + '\"}'
                redactedData.append(meanStr)
    return redactedData

    return(df)

def write_to_S3(redacted_df):
    pass

def write_to_S3(values, resourceType):
        # Store resources in a bundle prefixed by the resource type
    bucketNamePrefix = (resourceType+BUCKET_PREFIX).lower()

    matchingBucket = get_resource_buckets(bucketNamePrefix)
    if len(matchingBucket) > 1:
        raise AssertionError('Too many matching buckets found! '+ len(matchingBucket) + ' ' + str(matchingBucket))
    elif len(matchingBucket) == 1:
        bucketName = matchingBucket[0]
    else:
        bucketName, response = create_bucket(bucketNamePrefix, connection)
        tempFile = contentToFile(values, resourceType)
        # Generate a random prefix to the resource type
        fName = ''.join([str(uuid.uuid4().hex[:6]), resourceType])
        print("fName = " + fName + "resourceType = " + resourceType)
        write_to_bucket(bucketName, tempFile, fName)
        print("information written to bucket ", bucketName, ' as ', fName)

def read_from_kafka(consumer):
    # We want to get the patient id out of the passed Observation in order to use this to look up
    # records within the time window from FHIR
    unique_patient_ids = []
    fhirList = []

    for message in consumer:
        print("Read from from kafka topic " + kafka_topic + " at host: " + kafka_host)
        if TEST:
            resourceDict= json.loads(message)
        else:
            resourceDict = message.value
        print("type(resourceDict) = " + str(type(resourceDict)))
        print("resourceDict = " + str(resourceDict))
        try:
            if json.loads(resourceDict[0])['resourceType'] == 'Bundle':
                fhirList = json.loads(resourceDict[0])[
                    'entry']  # list of dictionary but we need to extract 'resource' value from each entry
            print("Bundle detected!")
        except:
            # If we don't have a bundle, then we are really good to go for resourceDict.  However, to be consistent with the
            # bundle path, push resourceDict into a fhirList as a string
            fhirList.append(str(resourceDict))
        print("read from Kafa done, type(fhirList) = " + str(type(fhirList)))
        print("fhirList = " + str(fhirList))
        for resource in fhirList:
            if type(resource) is dict:  # case of a bundle - still need to extract resource entry
                resourceDict = resource['resource']
                resourceType = resourceDict['resourceType']
                resource = str(resourceDict)
            else:
                resourceType = resourceDict['resourceType']

            print('resourceType = ', resourceType)
            # We only care about Observations here
            if resourceType != 'Observation':
                continue
    # Extract the patient id
            try:
                patient_id = resourceDict['subject']['reference']
            except:
                print("no subject->reference found in record " + str(resource))

            if patient_id not in unique_patient_ids:
                unique_patient_ids.append(patient_id)
    return(unique_patient_ids)

if __name__ == "__main__":
    main()