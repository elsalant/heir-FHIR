Preliminary - Setting up minio
1. Mac - first time install with Homebrew:
brew install minio/stable/minio
2. Start minio
minio server --address <port> <data location>
eg: minio server --address ":9000" /Users/eliot/projects/HEIR/code/data
On browser: http://127.0.0.1:9000 with minioadmin/minioadmin

3. Check an encryption key for the data:
Encryption key should be 32 bytes (chars) plain text key 
e.g.:
>32byteslongsecretkeymustbegive
4. Copy the data to the bucket:
Set up an alias to the bucket: -eg for an alias, "HEIR_STORE"
mc alias set HEIR_STORE http://localhost:9000 minioadmin minioadmin

mc cp <data source> ALIAS/<full path to bucket>/ --encrypt-key "ALIAS/<bucket name>/=<base64 key>"  [ADD THE "="]
e.g.:
mc cp --encrypt-key 'HEIR_STORE/Users/eliot/projects/HEIR/code/data/minio-bucket/=32byteslongsecretkeymustbegiven2' /Users/eliot/projects/synthea/output/fhir/A*.json HEIR_STORE/minio-bucket

>> To start the IBM FHIR Server docker image:
docker pull ibmcom/ibm-fhir-server
> Copy files in container from /home/default/transfers to config

docker run -p 9443:9443 -e BOOTSTRAP_DB=true -v /Users/eliot/projects/HEIR/code/transfers:/home/default/transfers ibmcom/ibm-fhir-server_els

>> IBM FHIR server in k8s:
helm install ibmfhir /Users/eliot/projects/HEIR/code/k8s/ibmfhir_server-0.1.0.tgz
kubectl port-forward svc/ibmfhir 9443:9443

>> To start Kafka k8s:
  helm install kafka bitnami/kafka

>> To create a Kafka client pod:
kubectl run kafka-client --restart='Never' --image docker.io/bitnami/kafka:2.8.0-debian-10-r43 --namespace heir-mvp --command -- sleep infinity

[NOT USED] >> To start docker Kafka:
zookeeper-server-start -daemon /usr/local/etc/kafka/zookeeper.properties & kafka-server-start /usr/local/etc/kafka/server.properties

1. In the synthea files, change bundle type from "transaction" to "batch"
"type": "transaction", -> "type": "batch"
   sed -i .bak 's/\"type\": \"transaction\"/\"type\": \"batch\"/g' *
2. Get all the files with the word "diabetes" and copy names into a file:
    grep diabetes *.json -l > diabetes_list.txt
3. Create a subdirectory, "diabetes" and copy all files in list to that subdirectory:
    while read -r line; do cp $line diabetes; done < diabetes_list.txt
4.  To load all fhir records in server:
for file in output/fhir/diabetes/*; do curl -k --location --request POST 'https://localhost:9443/fhir-server/api/v4' \
--header 'Content-Type: application/fhir+json' --user "fhiruser:change-password" --data-binary  "@$file"; done

To load a single record:
curl -k --location --request POST 'https://localhost:9443/fhir-server/api/v4' --header 'Content-Type: application/fhir+json' \
--user "fhiruser:change-password" --data-binary  "@/Users/eliot/projects/HEIR/code/data/diabetes/Abel832_Nitzsche158_d9b860b8-0b89-20a6-a7e1-74545fa8b3a3.json"


5. How to get a complete EHR for a specific patient:
curl -k --location --request GET 'https://127.0.01:9443/fhir-server/api/v4/Patient/17a96124508-f79963bb-ff31-4284-9c72-ca47e6c91fec/$everything' --user 'fhiruser:change-password' | jq

>> To check the Kafka topic queue:
kubectl  exec -it kafka-client -- kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic fhir-wp2 
