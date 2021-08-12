kubectl -n m4d-system create configmap policy --from-file=policy.rego
kubectl -n m4d-system label configmap policy openpolicyagent.org/policy=rego
while [[ $(kubectl get cm policy -n m4d-system -o 'jsonpath={.metadata.annotations.openpolicyagent\.org/policy-status}') != '{"status":"ok"}' ]]; do echo "waiting for policy to be applied" && sleep 5; done
