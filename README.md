Build the IBM FHIR Server docker image:

>> To start the IBM FHIR Server docker image:

#kind load docker-image ibmcom/ibm-fhir-server_els:latest --name <cluster name>
kind load docker-image ghcr.io/elsalant/ibm-fhir-server_els:latest --name heir-mvp

#helm install ibmfhir /Users/eliot/projects/HEIR/code/helm/ibmfhir_server-0.1.0.tgz -n fybrik-system
helm install ibmfhir /Users/eliot/projects/HEIR/code/helm/ibmfhir_server -n fybrik-system

kubectl port-forward svc/ibmfhir 9443:9443 -n fybrik-system

>> To start Kafka k8s:
  helm install kafka bitnami/kafka -n fybrik-system

Create a namespace for the mvp:
kubectl create namespace mvp

Install datashim:
kubectl apply -f https://raw.githubusercontent.com/datashim-io/datashim/master/release-tools/manifests/dlf.yaml

To build Docker image:
cd /Users/eliot/projects/HEIR/code/python
make docker-build

Push the image to Docker package repo
make docker-push

Push the Helm chart to the repo
make helm-login
  helm registry login -u elsalant -p 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 ghcr.io
make helm-verify

go to the directory with the Helm chart and do:
helm chart save <Helm chart directory> ghcr.io/elsalant/<chart image name>:tag   where the tag and image name need to be what is defined in Chart.yaml
helm chart save fhir-to-s3 ghcr.io/elsalant/fhir-to-s3-chart:0.0.1

Push the chart to the repo:
helm push ghcr.io/elsalant/<chart image name>:tag
   helm chart push ghcr.io/elsalant/fhir-to-s3-chart:0.0.1

from /Users/eliot/projects/HEIR/code/mvp:
Install the account, credentials and asset:
kubectl apply -f credentials-eliot-secret.yaml
kubectl apply -f asset.yaml
kubectl apply -f account-els.yaml
kubectl apply -f permissions.yaml

Apply the policies
/Users/eliot/projects/HEIR/code/mvp/applyPolicy.sh

kubectl edit cm cluster-metadata -n fybrik-system
and change theshire to UK

Install the module
kubectl apply -f fhirToS3module-els.yaml -n fybrik-system

Install the application (in mvp namespace)
kubectl apply -f mvpApplication-els.yaml -n mvp
 
Check the upload to S3:
curl -k --location --request POST 'https://localhost:9443/fhir-server/api/v4' --header 'Content-Type: application/fhir+json' \
--user "fhiruser:change-password" --data-binary  "@/Users/eliot/projects/HEIR/code/data/diabetes/samplePatient.json

-----------------------
Appendix

>> To create a Kafka client pod:
kubectl run kafka-client --restart='Never' --image docker.io/bitnami/kafka:2.8.0-debian-10-r43 --namespace heir-mvp --command -- sleep infinity

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
--user "fhiruser:change-password" --data-binary  "@/Users/eliot/projects/HEIR/code/data/diabetes/Abel832_Nitzsche158_d9b860b8-0b89-20a6-a7e1-74545fa8$
To load just patient data:
curl -k --location --request POST 'https://localhost:9443/fhir-server/api/v4/Patient' --header 'Content-Type: application/fhir+json' \
--user "fhiruser:change-password" --data-binary  "@/Users/eliot/projects/HEIR/code/data/diabetes/samplePatient.json"

To read the stored Patient information:
curl -k -i -u 'fhiruser:change-password' --request GET https://localhost:9443/fhir-server/api/v4/Patient
curl -k -i -u 'fhiruser:change-password' --request GET https://localhost:9443/fhir-server/api/v4/Patient/17d0430cff4-ba9750b8-7f71-4858-bd7d-6ee84a34cb2d

To load a single Observation:
curl -k --location --request POST 'https://localhost:9443/fhir-server/api/v4/Observation' --header 'Content-Type: application/fhir+json' \
--user "fhiruser:change-password" --data-binary  "@/Users/eliot/projects/HEIR/code/data/diabetes/sampleObservation.json"

curl -k -i -u 'fhiruser:change-password' --request GET "https://localhost:9443/fhir-server/api/v4/Observation?code=4548-4"
[QUOTATION MARKS REQUIRED!!]
curl -k -i -u 'fhiruser:change-password' --request GET "https://localhost:9443/fhir-server/api/v4/Observation?subject=Patient/f001"
To ADD values:
curl -k -i -u 'fhiruser:change-password' --request GET "https://localhost:9443/fhir-server/api/v4/Observation?code=http://loinc.org|4548-4"

5. How to get a complete EHR for a specific patient:
curl -k --location --request GET 'https://127.0.01:9443/fhir-server/api/v4/Patient/17a96124508-f79963bb-ff31-4284-9c72-ca47e6c91fec/$everything' --us$

>> To check the Kafka topic queue:
kubectl  exec -it kafka-client -- kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic fhir-wp2
