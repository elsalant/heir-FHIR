kubectl -n fybrik-system create configmap sql-policy --from-file=policy.rego
kubectl -n fybrik-system label configmap sql-policy openpolicyagent.org/policy=rego
while [[ $(kubectl get cm sql-policy -n fybrik-system -o 'jsonpath={.metadata.annotations.openpolicyagent\.org/policy-status}') != '{"status":"ok"}' ]]; do echo "waiting for policy to be applied" && sleep 5; done
