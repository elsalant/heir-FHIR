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
from kubernetes import client, config
import base64

DEFAULT_KAFKA_TOPIC = 'fhir-wp2'
DEFAULT_KAKFA_HOST = 'kafka.fybrik-system:9092'

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
    for bucket in bucketCollection:
        bucketList.append(str(bucket.name))
    matchingBuckets = [s for s in bucketList if searchPrefix in s]
    if (matchingBuckets):
        print("matchingBuckets = " + str(matchingBuckets))
    return matchingBuckets

def connect_to_kafka():
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

    print("starting module!!")

    CM_PATH = '/etc/conf/conf.yaml'
    cmDict = []

    try:
        with open(CM_PATH, 'r') as stream:
            cmReturn = yaml.safe_load(stream)
        print('cmReturn = ', cmReturn)
        cmDict = cmReturn.get('data', [])

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
#       print("Read from Kafka: ", message.value)
        print("Read from Kafka!")
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
            # Generate a random prefix to the resource type
            fName = ''.join([str(uuid.uuid4().hex[:6]), resourceType])
            print("fName = " + fName + "resourceType = " + resourceType)
            write_to_bucket(bucketName, tempFile, fName)
            print("information written to bucket ", bucketName, ' as ', fName)
    consumer.close()

if __name__ == "__main__":
    main()