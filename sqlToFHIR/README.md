### This is an example of Fybrik read module that uses REST protocol to connect to a FHIR server to obtain medical records.  Policies redact the information returned by the FHIR server or can even restrict access to a given resource type.


> Do once:
helm repo add elsheir https://elsalant.github.io/heir-FHIR/

1. Install fybrik from the instructions in: https://fybrik.io/v0.5/get-started/quickstart/
2. Start the IBM FHIR server service (out-of-box version):
helm install ibmfhir elsheir/ibmfhir_orig -n fybrik-system
3. Create a namespace for the sqlfhir demo:  
kubectl create namespace sql-fhir
3. Pull the files:
git pull https://github.com/elsalant/heir-FHIR.git
4. Install the policy:  
\<ROOT>/sqlToFHIR/applyPolicy.sh
5. kubectl edit cm cluster-metadata -n fybrik-system
and change theshire to UK
6. kubectl apply -f \<ROOT>/sqlToFHIR/asset.yaml
7. Apply the module
kubectl apply -f \<ROOT>/sqlToFHIR/sqlToFHIRmodule.yaml  
8. Apply the application
kubectl apply -f \<ROOT>/sqlToFHIR/sqlToFHIRapplication
9. Test
- a) Load database  
kubectl port-forward svc/ibmfhir -n fybrik-system 9443:9443  
\<ROOT>/sqlToFHIR/createPatient.sh
- b) Port-forward pod in fybrik-blueprints  
 kubectl get pods -n fybrik-blueprints  
eg: kubectl port-forward pod/\<POD ID> -n fybrik-blueprints 5559:5559
- c) curl http://localhost:5559/Patient

To test blocking a resource, change "Observation" in asset.yaml to "Patient" and reinstall yaml. 

#### DEVELOPMENT

1. To build Docker image:  
cd /Users/eliot/projects/HEIR/code/sqlToFHIR  
make docker-build  

Push the image to Docker package repo  
make docker-push

2. Push the Helm chart to the repo
export HELM_EXPERIMENTAL_OCI=1  
helm registry login -u elsalant -p \<PASSWORD> ghcr.io

Package the chart:  
helm package \<ROOT>/charts/sqlToFHIR  
Save then push the chart:  
helm chart save sql-to-fhir-chart-0.0.4.tgz ghcr.io/elsalant/sql-to-fhir-chart:0.0.4  
helm chart push ghcr.io/elsalant/sql-to-fhir-chart:0.0.4  

Update the index:  
helm repo index --url https://ghcr.io/elsalant/ --merge index.yaml .

##### Development hints
1. files/conf.yaml controls the format of the policy evaluation.  This will be written into a file mounted inside the pod running in the fybrik-blueprints namespace.
2. templates/deployment.yaml defines the mount point (e.g. /etc/conf/conf.yaml) for this file.
3. Redaction values defined in values.yaml will be ignored.  This information will be supplied by the manager and connectors.
4. The FHIR server can be queried directly by:
 - kubectl port-forward svc/ibmfhir 9443:9443 -n fybrik-system  
 - curl -k -u 'fhiruser:change-password' 'https://127.0.0.1:9443/fhir-server/api/v4/Patient'
