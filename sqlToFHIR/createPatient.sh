curl -k --location --request POST 'https://localhost:9443/fhir-server/api/v4/Patient' --header 'Content-Type: application/fhir+json' \
--user "fhiruser:change-password" --data-binary  "@/Users/eliot/projects/HEIR/code/mvp/testPatient.json"

