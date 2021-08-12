kubectl create deployment mvp-notebook --image=jupyter/base-notebook --port=8888 -- start.sh jupyter lab --LabApp.token=''
kubectl set env deployment mvp-notebook JUPYTER_ENABLE_LAB=yes
kubectl label deployment mvp-notebook app.kubernetes.io/name=mvp-notebook
kubectl wait --for=condition=available --timeout=120s deployment/mvp-notebook
kubectl expose deployment mvp-notebook --port=80 --target-port=8888
