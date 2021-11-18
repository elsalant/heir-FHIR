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
import ast
import time

from curlCommands import handleQuery
from datetime import date, datetime, timedelta, timezone
from string import Template

TEST = False

DEFAULT_KAFKA_TOPIC = 'fhir-wp2'
DEFAULT_KAKFA_HOST = 'kafka.fybrik-system:9092'
if TEST:
    DEFAULT_FHIR_HOST = 'https://localhost:9443'
else:
    DEFAULT_FHIR_HOST = 'https://ibmfhir.fybrik-system:9443'

TEST_POLICY = "[{'action': 'RedactColumn', 'description': 'redacting columns: [id, valueQuantity.value]', 'columns': ['id', 'valueQuantity.value'], 'options': {'redactValue': 'XXXXX'}}, {'action': 'Statistics', 'description': 'statistics on columns: [valueQuantity.value]', 'columns': ['valueQuantity.value']}]"

DEFAULT_FHIR_USER = 'fhiruser'
DEFAULT_FHIR_PW = 'change-password'

DEFAULT_TIMEWINDOW = 3560 #days - should be 14
HIGH_THRESHOLD_DEFAULT = 8.3
LOW_THRESHOLD_DEFAULT = 4

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
        "display": "Glucose [Moles/volume] in Body Fluid"  \
      }  \
    ]  \
  },  \
  "subject": {  \
    "reference": "Patient/f001",  \
    "display": "P. van de Heuvel"  \
  },  \
  "effectivePeriod": {  \
    "start": "2021-11-11T09:30:10+01:00"  \
  },  \
  "issued": "2021-11-11T15:30:10+01:00",  \
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

kafka_host = os.getenv("HEIR_KAFKA_HOST") if os.getenv("HEIR_KAFKA_HOST") else DEFAULT_KAKFA_HOST
fhir_host = os.getenv("HEIR_FHIR_HOST") if os.getenv("HEIR_FHIR_HOST") else DEFAULT_FHIR_HOST
fhir_user = os.getenv("HEIR_FHIR_USER") if os.getenv("HEIR_FHIR_USER") else DEFAULT_FHIR_USER
fhir_pw = os.getenv("HEIR_FHIR_PW") if os.getenv("HEIR_FHIR_PW") else DEFAULT_FHIR_PW
time_window = os.getenv("HEIR_TIMEWINDOW") if os.getenv("HEIR_TIMEWINDOW") else DEFAULT_TIMEWINDOW

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


def read_from_fhir(id):
    print("querying FHIR server for patient_id " + id)
    queryURL = fhir_host
    queryString = PATIENT_LOOKUP
    params = {'subject': id}
    auth = (fhir_user, fhir_pw)

    observationRecord = handleQuery(queryURL, queryString, auth, params, 'GET')
    # Strip the bundle information out and convert to data frame
    recordList = []
    try:
        for record in observationRecord['entry']:
            recordList.append(json.dumps(record['resource']))
    except:
        print("no entry in observationRecord!")
    jsonList = [ast.literal_eval(x) for x in recordList]
 #   observationDF = pd.DataFrame.from_records(jsonList)
    observationDF = pd.json_normalize(jsonList)
    return observationDF

def apply_policy(df, policies):
    redactedData = []
    # Redact df based on policy returned from the policy manager
    meanStr = ''
    stdStr = ''  # standard deviation
    tar = ''   # time above range
    tbr = ''   # time below range
    tir = ''   # time in range
    std = ''
    cleanPatientId = df['subject.reference'][0].replace('/', '-')
    print('inside apply_policy. Length policies = ', str(len(policies)), " type(policies) = ", str(type(policies)))
#    for policy in policies:
    policy = policies
    print('policy = ', str(policy))
    action = policy['transformations'][0]['action']
    if action == 'DeleteColumn':
        print('DeleteColumn called!')
        for col in policy['transformations'][0]['columns']:
            df.drop(col, inplace=True, axis=1)
        redactedData.append(df.to_json())
        output_results(cleanPatientId, str(redactedData))
    if action == 'Statistics':
        for col in policy['transformations'][0]['columns']:
            print('col = ', col)
            try:
                std = df[col].std()
            except:
                print('No col ' + col + ' found!')
                print(df.keys())
            stdStr = '{\"CGM_STD\": \"' + str(std) + '\"}'
            mean = df[col].mean()
            meanStr = '{\"CGM_MEAN\": \"' + str(mean) + '\"}'
        redactedData.append(meanStr+ ' ' + stdStr)
# Calculate Time in Range, Time Above Range, Time Below Range
        numObservations = len(df)
        try:
            high_threshold = df['referenceRange'][0][0]['high']['value']
            print('high_threshold found in resource as ' + str(high_threshold))
        except:
            high_threshold = HIGH_THRESHOLD_DEFAULT
        try:
            low_threshold = df['referenceRange'][0][0]['low']['value']
            print('low_threshold found in resource as ' + str(low_threshold))
        except:
            low_threshold = LOW_THRESHOLD_DEFAULT
        tar = round((len(df.loc[df[col]>high_threshold,col])/numObservations)*100)
        tbr = round((len(df.loc[df[col]<low_threshold,col])/numObservations)*100)
        tir = 100 - tar - tbr
        d = {
            'PATIENT_ID': df['subject.reference'][0],
            'CGM_TIR': tir,
            'CGM_TAR': tar,
            'CGM_TBR': tbr,
            'CGM_MEAN': mean,
            'CGM_STD': std
        }
        output_results(cleanPatientId,d)
        redactedData = d
    print("returning redacted data " + str(redactedData))

def timeWindow_filter(df):
    # drop rows that are outside of the timeframe
    df.drop(df.loc[(pd.to_datetime(df['effectivePeriod.start'], utc=True) + timedelta(days=time_window) < datetime.now(timezone.utc)) | (df['resourceType'] != 'Observation')].index, inplace=True)
    return df


def write_to_S3(patientId, values):
    # Store resources in a bundle prefixed by the resource type
    bucketNamePrefix = (patientId + BUCKET_PREFIX).lower()

    matchingBucket = get_resource_buckets(bucketNamePrefix)
    if len(matchingBucket) > 1:
        raise AssertionError('Too many matching buckets found! ' + len(matchingBucket) + ' ' + str(matchingBucket))
    elif len(matchingBucket) == 1:
        bucketName = matchingBucket[0]
    else:
        bucketName, response = create_bucket(bucketNamePrefix, connection)
        tempFile = contentToFile(values, patientId)
        # Generate a random prefix to the resource type
        fName = ''.join([str(uuid.uuid4().hex[:6]), patientId])
        print("fName = " + fName + "patientId = " + patientId)
        write_to_bucket(bucketName, tempFile, fName)
        print("information written to bucket ", bucketName, ' as ', fName)

def read_from_kafka(consumer, cmDict):
    # We want to get the patient id out of the passed Observation in order to use this to look up
    # records within the time window from FHIR
    unique_patient_ids = []
    fhirList = []

    for message in consumer:
        print("Read from from kafka topic " + kafka_topic + " at host: " + kafka_host)
        if TEST:
            resourceDict = json.loads(message)
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
                patient_id = resourceDict['subject][reference]']
            except:
                patient_id = resourceDict['subject_reference']   #flattened schema
            print('patient_id = ', str(patient_id))

            if patient_id not in unique_patient_ids:
                unique_patient_ids.append(patient_id)
        if TEST:
            policies = TEST_POLICY
        else:
            policies = cmDict

 #       policyJson = json.dumps(policies)

        for id in unique_patient_ids:
            df = read_from_fhir(id)
            filteredDF = timeWindow_filter(df)
            redacted_df = apply_policy(filteredDF, policies)
        if not TEST:
            consumer.close()

def output_results(patientId, outvalues):
    with open('noklus_patient_observation_template.xml', 'r') as f:
        src = Template(f.read())
        result = src.substitute(outvalues)
        print('output_results: result = ',result)
        write_to_S3(patientId, result)
    f.close()

def main():
    global connection
    global kafka_topic
    global kafka_host
    global fhir_host
    global fhir_pw
    global fhir_user

    print("starting module!!")

    CM_PATH = '/etc/conf/conf.yaml' # from the "volumeMounts" parameter in templates/deployment.yaml

    cmReturn = ''
    cmDict = {}

    if not TEST:
        tries = 3
        try_opening = True
        while try_opening:
            try:
                try:
                    with open(CM_PATH, 'r') as stream:
                        cmReturn = yaml.safe_load(stream)
                    try_opening = False
                except Exception as e:
                    tries -= 1
                    print(e.args)
                    if (tries == 0):
                        try_opening = False
                        raise ValueError('Error reading from file! ', CM_PATH)
                    time.sleep(108)
            except ValueError as e:
                print(e.args)

        print('cmReturn = ', cmReturn)
        if TEST:
            cmDict = "dict_items([('WP2_TOPIC', 'fhir-wp2'), ('HEIR_KAFKA_HOST', 'kafka.fybrik-system:9092'), ('VAULT_SECRET_PATH', None), ('SECRET_NSPACE', 'fybrik-system'), ('SECRET_FNAME', 'credentials-els'), ('S3_URL', 'http://s3.eu.cloud-object-storage.appdomain.cloud'), ('transformations', [{'action': 'RedactColumn', 'description': 'redacting columns: [id valueQuantity.value]', 'columns': ['id', 'valueQuantity.value'], 'options': {'redactValue': 'XXXXX'}}, {'action': 'Statistics', 'description': 'statistics on columns: [valueQuantity.value]', 'columns': ['valueQuantity.value']}])])"
        else:
            cmDict = cmReturn.get('data', [])
        print("cmDict = ", cmDict.items())

        s3_URL = cmDict['S3_URL']

        secret_namespace = cmDict['SECRET_NSPACE']
        secret_fname = cmDict['SECRET_FNAME']

        print("secret_namespace = " + secret_namespace + ", secret_fname = " + secret_fname)
        s3_access_key, s3_secret_key = getSecretKeys(secret_fname, secret_namespace)
        print("access key found: " + s3_access_key + ", secret_key found: " + s3_secret_key)

        print("s3_URL = ", str(s3_URL))

        assert s3_access_key != '', 'No s3_access key found!'
        assert s3_secret_key != '', 'No s3_secret_key found!'

        connection = boto3.resource(
            's3',
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key,
            endpoint_url=s3_URL
        )
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
    read_from_kafka(consumer, cmDict)   #does not return from this call

if __name__ == "__main__":
    main()
