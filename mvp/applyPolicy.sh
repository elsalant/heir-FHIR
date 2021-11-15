kubectl -n fybrik-system create configmap mvp-policy --from-file=mvp-policy.rego
kubectl -n fybrik-system label configmap mvp-policy openpolicyagent.org/policy=rego
while [[ $(kubectl get cm mvp-policy -n fybrik-system -o 'jsonpath={.metadata.annotations.openpolicyagent\.org/policy-status}') != '{"status":"ok"}' ]]; do echo "waiting for policy to be applied" && sleep 5; done
