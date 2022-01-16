### This is an example of Fybrik read module that uses REST protocol to connect to a FHIR server to obtain medical records.  Policies redact the information returned by the FHIR server or can even restrict access to a given resource type.


Do once:  make sure helm v3.7+ is installed
> helm version

1. Install fybrik from the instructions in: https://fybrik.io/v0.6/get-started/quickstart/
2. Start the IBM FHIR server service (out-of-box version):
helm install ibmfhir oci://ghcr.io/elsalant/ibmfhir_orig --version=0.2.0 -n fybrik-system
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
- To load Observations:  
  docker run --network host ghcr.io/elsalant/observation-generator:v1
(NOTE: On MacOS, the "--network" switch may not work.  In that case, it might be easiest to port-forward the fhir server and 
then run observationGenerator.py from a local Python environment
e.g.  
  a) kubectl port-forward svc/ibmfhir -n fybrik-system 9443:9443
  b) python3 observationGenerator.py (under heir-FHIR/python/observationGenerator.py)

#### Hints
To test redaction: pick a field in the resource (e.g. "id") and set the tag in the asset.yaml file to "PII".
Note that to redact a given field in a given resource, e.g. "id" in "Patient" sources, in the asset.yaml file, specify the componentsMetadata value as "Patient.id".

If either the asset or policy is changed, then the Fybrik application needs to be restarted:
kubectl delete -f <name of FybrikApplication file>  
kubectl apply -f <name of FybrikApplication file>
 
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
helm package ibmfhir-orig -d /tmp
Push to repo: 
helm push /tmp/ibmfhir_orig-0.2.0.tgz oci://ghcr.io/elsalant

[IS THIS NEEDED??] Update the index:  
helm repo index --url https://ghcr.io/elsalant/ --merge index.yaml .

##### Development hints
1. files/conf.yaml controls the format of the policy evaluation.  This will be written into a file mounted inside the pod running in the fybrik-blueprints namespace.
2. templates/deployment.yaml defines the mount point (e.g. /etc/conf/conf.yaml) for this file.
3. Redaction values defined in values.yaml will be ignored.  This information will be supplied by the manager and connectors.
4. The FHIR server can be queried directly by:
 - kubectl port-forward svc/ibmfhir 9443:9443 -n fybrik-system  
 - curl -k -u 'fhiruser:change-password' 'https://127.0.0.1:9443/fhir-server/api/v4/Patient'
