1. Install fybrik from the instructions in: https://fybrik.io/v0.5/get-started/quickstart/
2. Start Kafka server:
   helm repo add bitnami https://charts.bitnami.com/bitnami
   helm install kafka bitnami/kafka -n fybrik-system
3. Start the IBM FHIR server with Interceptor
#   helm install ibmfhir /Users/eliot/projects/HEIR/code/helm/ibmfhir_server -n fybrik-system
    helm install ibmfhir ghcr.io/elsalant/ibmfhir_server:v1 -n fybrik-system
4. Create a namespace for mvp application use
   kubectl create namespace mvp
5. Install datashim:
   kubectl apply -f https://raw.githubusercontent.com/datashim-io/datashim/master/release-tools/manifests/dlf.yaml
6. Install the account, credentials and asset:
   kubectl apply -f credentials-eliot-secret.yaml
   kubectl apply -f asset.yaml
   kubectl apply -f account-els.yaml
   kubectl apply -f permissions.yaml
7. Apply the policies
   /Users/eliot/projects/HEIR/code/mvp/applyPolicy.sh
8. kubectl edit cm cluster-metadata -n fybrik-system
   and change theshire to UK
9. Install the module
   kubectl apply -f fhirToS3module.yaml -n fybrik-system
10. Install the application (in mvp namespace)
   kubectl apply -f mvpApplication.yaml -n mvp
11. To load a single Observation:
   curl -k --location --request POST 'https://localhost:9443/fhir-server/api/v4/Observation' --header 'Content-Type: application/fhir+json' \
--user "fhiruser:change-password" --data-binary  "@/Users/eliot/projects/HEIR/code/data/diabetes/sampleObservation.json"

12. The emulator can be run:
    python3 observationGenerator.py
