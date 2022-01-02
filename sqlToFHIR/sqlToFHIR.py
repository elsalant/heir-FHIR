from flask import Flask, request
from kubernetes import client, config
import requests
import yaml
import urllib.parse as urlparse
import curlify
import urllib.parse
import json
import time
from datetime import date, datetime, timedelta, timezone
import pandas as pd
import os
import re
import base64

FLASK_PORT_NUM = 5559  # this application

ACCESS_DENIED_CODE = 403
ERROR_CODE = 406
VALID_RETURN = 200

TEST = False

if TEST:
    DEFAULT_FHIR_HOST = 'https://localhost:9443/fhir-server/api/v4/'
else:
    DEFAULT_FHIR_HOST = 'https://ibmfhir.fybrik-system:9443/fhir-server/api/v4/'
DEFAULT_FHIR_USER = 'fhiruser'
DEFAULT_FHIR_PW = 'change-password'

DEFAULT_TIMEWINDOW = 3560  # days - should be 14
HIGH_THRESHOLD_DEFAULT = 8.3
LOW_THRESHOLD_DEFAULT = 4

fhir_host = os.getenv("HEIR_FHIR_HOST") if os.getenv("HEIR_FHIR_HOST") else DEFAULT_FHIR_HOST
fhir_user = os.getenv("HEIR_FHIR_USER") if os.getenv("HEIR_FHIR_USER") else DEFAULT_FHIR_USER
fhir_pw = os.getenv("HEIR_FHIR_PW") if os.getenv("HEIR_FHIR_PW") else DEFAULT_FHIR_PW
time_window = os.getenv("HEIR_TIMEWINDOW") if os.getenv("HEIR_TIMEWINDOW") else DEFAULT_TIMEWINDOW

app = Flask(__name__)
cmDict = {}

def handleQuery(queryGatewayURL, queryString, auth, params, method):
  #  print("querystring = " + queryString)
    queryStringsLessBlanks = re.sub(' +', ' ', queryString)

    curlString = queryGatewayURL + urllib.parse.unquote_plus(queryStringsLessBlanks)
 #   curlString = queryGatewayURL + str(base64.b64encode(queryStringsLessBlanks.encode('utf-8')))
    print("curlCommands: curlString = ", curlString)
    try:
      if (method == 'POST'):
        r = requests.post(curlString, auth=auth, params=params, verify=False)
      else:
        r = requests.get(curlString, auth=auth, params=params, verify=False)
    except Exception as e:
      print("Exception in handleQuery, curlString = " + curlString + ", auth = " + str(auth))
      print(e.args)
      return(ERROR_CODE)

    print("curl request = " + curlify.to_curl(r.request))
 #   if r.status_code != 200:
 #       return None
    if (r.status_code == 404):
      print("handleQuery: empty return!")
      return(None)
    else:
      try:
        returnList = r.json()  # decodes the response in json
      except:
        print('curlCommands: curl return is not in JSON format! Returing as binary')
        returnList = r.content
#    if re.response is None:
#        print("---> error on empty returnList in curlCommands.py")
#    else:
 #       print('[%s]' % ', '.join(map(str, returnList)))

    return (returnList)

def getSecretKeys(secret_name, secret_namespace):  # Not needed here.  Maybe in JWT is pushed into a secret key?
    try:
        config.load_incluster_config()  # in cluster
    except:
        config.load_kube_config()   # useful for testing outside of k8s
    v1 = client.CoreV1Api()
    secret = v1.read_namespaced_secret(secret_name, secret_namespace)
    accessKeyID = base64.b64decode(secret.data['access_key'])
    secretAccessKey = base64.b64decode(secret.data['secret_key'])
    return(accessKeyID.decode('ascii'), secretAccessKey.decode('ascii'))

def read_from_fhir(queryString):
    queryURL = fhir_host
    params = ''
    auth = (fhir_user, fhir_pw)

    returnedRecord = handleQuery(queryURL, queryString, auth, params, 'GET')
    if returnedRecord == None:
        return("No results returned!")
    # Strip the bundle information out and convert to data frame
    recordList = []
    try:
        for record in returnedRecord['entry']:
            recordList.append(json.dumps(record['resource']))
    except:
        print("no information returned!")
#    jsonList = [ast.literal_eval(x) for x in recordList]
    jsonList = [json.loads(x) for x in recordList]
    return (jsonList, VALID_RETURN)

def apply_policy(jsonList, policies):
    df = pd.json_normalize(jsonList[0])
    redactedData = []
    # Redact df based on policy returned from the policy manager
    meanStr = ''
    stdStr = ''  # standard deviation
    std = ''
   # cleanPatientId = df['subject.reference'][0].replace('/', '-')
    print('inside apply_policy. Length policies = ', str(len(policies)), " type(policies) = ", str(type(policies)))
#    for policy in policies:
    if TEST:
        policy = dict(policies['dict_item'])
    else:
        policy = policies
    print('policy = ', str(policy))
    action = policy['transformations'][0]['action']
    if action == '':
        return (str(df.to_json()))
    if action == 'DeleteColumn':
        print('DeleteColumn called!')
        try:
            for col in policy['transformations'][0]['columns']:
                df.drop(col, inplace=True, axis=1)
        except:
            print("No such column " + col + " to delete")
        redactedData.append(df.to_json())
        return(str(redactedData))

    if action == 'RedactColumn':
        print('RedactColumn called!')
        replacementStr = policy['transformations'][0]['options']['redactValue']
        for col in policy['transformations'][0]['columns']:
            try:
                df[col].replace(r'.+', replacementStr, regex=True, inplace=True)
            except:
                print("No such column " + col + " to redact")
        redactedData.append(df.to_json())
        return(str(redactedData))

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
        return(d)

def timeWindow_filter(df):
    print("keys = ", df.keys())
    # drop rows that are outside of the timeframe
    df.drop(df.loc[(pd.to_datetime(df['effectivePeriod.start'], utc=True) + timedelta(days=time_window) < datetime.now(timezone.utc)) | (df['resourceType'] != 'Observation')].index, inplace=True)
    return df

# @app.route('/query/<queryString>')
# def query(queryString):
# Catch anything
@app.route('/<path:queryString>',methods=['GET', 'POST', 'PUT'])
def getAll(queryString=None):
    global cmDict
    print("queryString = " + queryString)
    print('request.url = ' + request.url)

    # Go out to the actual FHIR server
    print("request.method = " + request.method)
    dfBack = read_from_fhir(queryString)
    if (dfBack is None):
        return ("No results returned")
#apply_policies
    ans = apply_policy(dfBack, cmDict)
    return (ans)

def main():
    global cmDict

    print("starting module!!")

    CM_PATH = '/etc/conf/conf.yaml' # from the "volumeMounts" parameter in templates/deployment.yaml

    cmReturn = ''

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
                    time.sleep(5)
            except ValueError as e:
                print(e.args)

        print('cmReturn = ', cmReturn)
    if TEST:
        cmDict = {'dict_item': [('WP2_TOPIC', 'fhir-wp2'), ('HEIR_KAFKA_HOST', 'kafka.fybrik-system:9092'),('transformations', [{'action': 'RedactColumn', 'description': 'redacting columns: [id valueQuantity.value]', 'columns': ['id', 'valueQuantity.value'], 'options': {'redactValue': 'XXXXX'}}, {'action': 'Statistics', 'description': 'statistics on columns: [valueQuantity.value]', 'columns': ['valueQuantity.value']}])]}
  #      cmDict = {'dict_items': [('WP2_TOPIC', 'fhir-wp2'), ('HEIR_KAFKA_HOST', 'kafka.fybrik-system:9092'), ('VAULT_SECRET_PATH', None), ('SECRET_NSPACE', 'fybrik-system'), ('SECRET_FNAME', 'credentials-els'), ('S3_URL', 'http://s3.eu.cloud-object-storage.appdomain.cloud'), ('transformations', [{'action': 'RedactColumn', 'description': 'redacting columns: [id valueQuantity.value]', 'columns': ['id', 'valueQuantity.value'], 'options': {'redactValue': 'XXXXX'}}, {'action': 'Statistics', 'description': 'statistics on columns: [valueQuantity.value]', 'columns': ['valueQuantity.value']}])]}
    else:
        cmDict = cmReturn.get('data', [])
    print("cmDict = ", cmDict)

    app.run(port=FLASK_PORT_NUM, host='0.0.0.0')

if __name__ == "__main__":
    main()