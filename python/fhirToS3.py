''' Copies FHIR resource in JSON from Kafka queue to S3 bucket.  The bucket name will
correspond to the resource name.
No buffering of resources is done on the write - this can be achieved by configuring Kafka for batching'''
import json
import boto3
import tempfile

import uuid
import os

import yaml
from kafka import KafkaConsumer
from json import loads

DEFAULT_KAFKA_TOPIC = 'fhir-wp2'
DEFAULT_KAKFA_HOST = 'kafka.fybrik-system:9092'

connectionDict = json.loads('{ \
  "apikey": "-8qkZdzf4o8GhEBjG3n8jwJyNYLprPRTZezqvM69NFub", \
  "cos_hmac_keys": { \
    "access_key_id": "65608160e74c42409da64c808575f994", \
    "secret_access_key": "4e95c96e7fe67001c07617c55051140ba0ad4f958c37b335" }, \
  "endpoints": "https://control.cloud-object-storage.cloud.ibm.com/v2/endpoints", \
  "iam_apikey_description": "Auto-generated for key 65608160-e74c-4240-9da6-4c808575f994", \
  "iam_apikey_name": "heir-mvp", \
  "iam_role_crn": "crn:v1:bluemix:public:iam::::serviceRole:Writer", \
  "iam_serviceid_crn": "crn:v1:bluemix:public:iam-identity::a/285dff93a1c4f6708ad25651e4d16ad0::serviceid:ServiceId-74022536-f7e6-46ba-9dda-8d5eb96f7d4c", \
  "resource_instance_id": "crn:v1:bluemix:public:cloud-object-storage:global:a/285dff93a1c4f6708ad25651e4d16ad0:8d7ba9f9-307e-47fd-bb75-2f558f3f4198::" \
}')

DEFAULT_S3_URL = 'http://s3.ap.cloud-object-storage.appdomain.cloud'
DEFAULT_ACCESS_KEY = connectionDict['cos_hmac_keys']['access_key_id']
DEFAULT_SECRET_KEY = connectionDict['cos_hmac_keys']['secret_access_key']

#kafka_topic = os.getenv("WP2_TOPIC") if os.getenv("WP2_TOPIC") else DEFAULT_KAFKA_TOPIC
#kafka_host = os.getenv("HEIR_KAFKA_HOST") if os.getenv("HEIR_KAFKA_HOST") else DEFAULT_KAKFA_HOST

s3_URL = os.getenv("S3_URL") if os.getenv("S3_URL") else DEFAULT_S3_URL
s3_access_key = os.getenv("access_key_id") if os.getenv("access_key_id") else DEFAULT_ACCESS_KEY
s3_secret_key = os.getenv("secret_access_key") if os.getenv("secret_access_key") else DEFAULT_SECRET_KEY

if os.getenv("access_key_id"):
    print("access_key_id env found!")
BUCKET_PREFIX = '-heir-'
TEST = False

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

TEST_DATA = '{ \
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

def get_resource_buckets(searchPrefix):
    # Get a bucket with a name that contains the passed prefix
    bucketCollection = connection.buckets.all()
    bucketList = []
    print('Printing bucket names...')
    for bucket in bucketCollection:
        print(f'Bucket Name: {bucket.name}')
        bucketList.append(bucket.name)
    matchingBuckets = [s for s in bucketList if searchPrefix in s]
    return matchingBuckets

def connect_to_kafka():
    consumer = None
    try:
        consumer = KafkaConsumer(
            kafka_topic,
            bootstrap_servers=[kafka_host],
            group_id=kafka_topic,
            value_deserializer=lambda x: loads(x.decode('utf-8')))
    except:
        raise Exception("Kafka did not connect for host " + kafka_host + " and  topic " + kafka_topic)

    print("Connection to kafka at host " + kafka_host + " and  topic " + kafka_topic + " succeeded!")
    return consumer

def read_from_kafka(consumer):
    resourceList = []
    if TEST:
        resourceList.append(TEST_BUNDLE_DATA)
    for message in consumer:
        print("Read from Kafka: ", message.value)
        resourceList.append(message.value)
    return(resourceList)

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
        bucketObject.upload_file(tempFile.name)
    finally:
        tempFile.close()

def main():
    global connection
    global kafka_topic
    global kafka_host

    print("starting module!!")

    s3_URL = DEFAULT_S3_URL
    s3_access_key = DEFAULT_ACCESS_KEY
    s3_secret_key = DEFAULT_SECRET_KEY

    CM_PATH = '/etc/conf/conf.yaml'
    cmDict = []

    try:
        with open(CM_PATH, 'r') as stream:
            cmReturn = yaml.safe_load(stream)
        print('cmReturn = ', cmReturn)
        cmDict = cmReturn.get('data', [])
        print("cmDict['WP2_TOPIC'] = ", cmDict['WP2_TOPIC'])

        kafka_host = os.getenv("HEIR_KAFKA_HOST") if os.getenv("HEIR_KAFKA_HOST") else DEFAULT_KAKFA_HOST
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

    s3_URL = os.getenv("S3_URL") if os.getenv("S3_URL") else DEFAULT_S3_URL
    s3_access_key = os.getenv("access_key_id") if os.getenv("access_key_id") else DEFAULT_ACCESS_KEY
    s3_secret_key = os.getenv("secret_access_key") if os.getenv("secret_access_key") else DEFAULT_SECRET_KEY

    connection = boto3.resource(
        's3',
        aws_access_key_id = s3_access_key,
        aws_secret_access_key = s3_secret_key,
        endpoint_url = s3_URL
    )

    consumer = connect_to_kafka()
    print(" Waiting to read from kafka topic " + kafka_topic + " at host: " + kafka_host)
    fhirList = []
    if TEST:
        fhirList.append(TEST_BUNDLE_DATA)
    for message in consumer:
        print("Read from Kafka: ", message.value)
        resourceDict = message.value
        print("type(resourceDict) = " + str(type(resourceDict)))
        print("resourceDict = " + str(resourceDict))
        try:
            if json.loads(resourceDict[0])['resourceType'] == 'Bundle':
                fhirList = json.loads(resourceDict[0])['entry']   # list of dictionary but we need to extract 'resource' value from each entry
            print("Bundle detected!")
        except:
            # If we don't have a bundle, then we are really good to go for resourceDict.  However, to be consistent with the
            # bundle path, push resourceDict into a fhirList as a string
            fhirList.append(str(resourceDict))
        print("read from Kafa done, type(fhirList) = " + str(type(fhirList)))
        print("fhirList = " + str(fhirList))
        for resource in fhirList:
            if type(resource) is dict:   # case of a bundle - still need to extract resource entry
                resourceDict = resource['resource']
                resourceType = resourceDict['resourceType']
                resource = str(resourceDict)
            else:
                resourceType = resourceDict['resourceType']

            print('resourceType = ', resourceType)
        # Store resources in a bundle prefixed by the resource type
            bucketNamePrefix = (resourceType+BUCKET_PREFIX).lower()

            matchingBucket = get_resource_buckets(bucketNamePrefix)
            if len(matchingBucket) > 1:
                raise AssertionError('Too many matching buckets found! '+ len(matchingBucket) + ' ' + str(matchingBucket))
            elif len(matchingBucket) == 1:
                bucketName = matchingBucket[0]
            else:
                bucketName, response = create_bucket(bucketNamePrefix, connection)
            tempFile = contentToFile(resource, resourceType)
            fName = ''.join([str(uuid.uuid4().hex[:6]), resourceType])
            write_to_bucket(bucketName, tempFile, fName)
            print("information written to bucket ", bucketName, ' as ', fName)
    consumer.close()

if __name__ == "__main__":
    main()