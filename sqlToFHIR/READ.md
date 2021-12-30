Install fybrik from the instructions in: https://fybrik.io/v0.5/get-started/quickstart/

To create the code that takes a FHIR query and executes it against the FHIR server.  (Not SQL...)
* NOTE: We can really run the standard IBM FHIR server here and not the modified one with the interceptor.  Need to change the following 
* installation.  In that case, we don't need kafka
>> To start Kafka k8s:
  helm install kafka bitnami/kafka -n fybrik-system
1. Start the IBM FHIR server service:
helm install ibmfhir /Users/eliot/projects/HEIR/code/helm/ibmfhir_server -n fybrik-system
2. Create a namespace for the sqlfhir demo
kubectl create namespace sql-fhir
3. Install datashim:
kubectl apply -f https://raw.githubusercontent.com/datashim-io/datashim/master/release-tools/manifests/dlf.yaml
4. Install the policy
/Users/eliot/projects/HEIR/code/sqlToFHIR/applyPolicy.sh
5. kubectl edit cm cluster-metadata -n fybrik-system
and change theshire to UK
6. kubectl apply -f /Users/eliot/projects/HEIR/code/sqlToFHIR/asset.yaml
7. Apply the module
kubectl apply -f /Users/eliot/projects/HEIR/code/sqlToFHIR/sqlToFHIRmodule.yaml -n sql-fhir
8. Apply the application
kubectl apply -f /Users/eliot/projects/HEIR/code/sqlToFHIR/sqlToFHIRapplication
9. Test
a) Load database 
/Users/eliot/projects/HEIR/code/sqlToFHIR/createPatient.sh
b) curl http://localhost:5559/Patient

DEVELOPMENT

4. To build Docker image:
cd /Users/eliot/projects/HEIR/code/sqlToFHIR
make docker-build

Push the image to Docker package repo
make docker-push

Push the Helm chart to the repo
export HELM_EXPERIMENTAL_OCI=1
make helm-login
  helm registry login -u elsalant -p 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 ghcr.io
make helm-verify

go to the directory with the Helm chart and do:
helm chart save <Helm chart directory> ghcr.io/elsalant/<chart image name>:tag   where the tag and image name need to be what is defined in Chart.yaml
helm chart save sqlToFHIR ghcr.io/elsalant/sql-to-fhir-chart:0.0.1

Push the chart to the repo:
helm push chart ghcr.io/elsalant/<chart image name>:tag
   helm chart push ghcr.io/elsalant/sql-to-fhir-chart:0.0.1
