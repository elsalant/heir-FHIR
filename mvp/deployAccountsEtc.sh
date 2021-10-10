kubectl apply -f asset.yaml
kubectl apply -f credentials-heir.yaml
kubectl apply -f account-heir.yaml
kubectl apply -f credentials-eliot-secret.yaml
kubectl apply -f permissions.yaml
kubectl apply -f https://raw.githubusercontent.com/datashim-io/datashim/master/release-tools/manifests/dlf.yaml
