FROM ibmcom/ibm-fhir-server:4.8.3
COPY --chown=1001:0 fhir-server-config.json /opt/ol/wlp/usr/servers/defaultServer/config/default
COPY transfers/* userlib
COPY java/HeirInterceptor.jar userlib

