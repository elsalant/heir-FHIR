Instructions for installing the MVP demo - takes a 2-week snapshot of Observation data from
the IBM FHIR server, performs statisical analysis on it, and writes the data out to s3.
Note that the FHIR server has been modified to include interceptor code to write received 
Observation records out to a Kafka queue.  The Fybrik module will read from the Kafka queue, and 
retrieve the 2 week snapshot data based on the id in the received Observation.

Do once:
> Clone these files:  
git clone https://github.com/elsalant/heir-FHIR.git  
> Install kind if required (https://kind.sigs.k8s.io/docs/user/quick-start/) and create a new kind cluster:  
kind create cluster --name mvp 
> Add to the list of helm repos  
- helm repo add bitnami https://charts.bitnami.com/bitnami
- helm repo update

> IMPORTANT!!
>  Make sure helm is at least at v3.7.2  
check using $helm version

After installing Helm:  
export HELM_EXPERIMENTAL_OCI=1

1. Install fybrik from the instructions in: https://fybrik.io/v0.6/get-started/quickstart/
2. Start the Kafka server:  
   - helm install kafka bitnami/kafka -n fybrik-system
3. Start the IBM FHIR server with the Interceptor
    helm install ibmfhir oci://ghcr.io/elsalant/ibmfhir_server --version=0.2.0 -n fybrik-system  
4. Create a namespace for mvp application use  
   kubectl create namespace mvp
5. Install datashim:  
   kubectl apply -f https://raw.githubusercontent.com/datashim-io/datashim/master/release-tools/manifests/dlf.yaml

Move to the mvp directory  

6. Edit credentials-heir.yaml and add the s3 access and secret keys (in two places) then:  
   kubectl apply -f credentials-heir.yaml
7. Edit account-heir.yaml and configure the endpoint for your s3 store, then apply:  
   kubectl apply -f account-heir.yaml
8. Install the asset description and permissions:  
   - kubectl apply -f https://raw.githubusercontent.com/elsalant/heir-FHIR/main/mvp/asset.yaml
   - kubectl apply -f https://raw.githubusercontent.com/elsalant/heir-FHIR/main/mvp/permissions.yaml
7. Apply the policies:   
  mvp/applyPolicy.sh
8. kubectl edit cm cluster-metadata -n fybrik-system  
   and change "theshire" ("Region" tag) to "UK"
9. Install the module  
   kubectl apply -f https://raw.githubusercontent.com/elsalant/heir-FHIR/main/mvp/fhirToS3module.yaml -n fybrik-system
10. Install the application (in mvp namespace)  
   kubectl apply -f https://raw.githubusercontent.com/elsalant/heir-FHIR/main/mvp/mvpApplication.yaml -n mvp
You can confirm that the application is running by entering:  
kubectl get pods -n fybrik-blueprints

To load the FHIR server:  (do this in a new window)  
   kubectl port-forward svc/ibmfhir -n fybrik-system 9443:9443  
12. The emulator to generate Observation records can be run by:  
   docker run --network host ghcr.io/elsalant/observation-generator:v1    

### Developer Notes
To package and push a chart:  
from the charts directory:  
- helm package ibmfhir_server -d /tmp
- helm push /tmp/ibmfhir_server-0.2.0.tgz oci://ghcr.io/elsalant
