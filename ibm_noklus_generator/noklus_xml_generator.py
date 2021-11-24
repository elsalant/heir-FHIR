import json
import math
from datetime import date, datetime, time, timedelta, timezone
from string import Template
import fhirclient.server
import fhirclient.models.observation as o

smart = fhirclient.server.FHIRServer(None, 'https://fhiruser:change-password@localhost:9443/fhir-server/api/v4')

def pretty(js):
    return json.dumps(js, indent=2)

def datetime_in_range(start, end, x):
    if start <= end:
        return start <= x <= end
    else:
        return start <= x or x <= end

def convert_to_mmol_l(val):
    return val/18.2

def generate_patient_file(patient_id, tir, tar, tbr, mean, std):
    d = {
        'PATIENT_ID': patient_id,
        'CGM_TIR': tir,
        'CGM_TAR': tar,
        'CGM_TBR': tbr,
        'CGM_MEAN': mean,
        'CGM_STD': std
    }

    with open('noklus_patient_observation_template.xml', 'r') as f:
        src = Template(f.read())
        result = src.substitute(d)
        print(result)

def get_normalized_values(observations):
    values = []
    for observation in observations:
        if (observation.valueQuantity.unit == 'mg/dL'):
            values.append(convert_to_mmol_l(observation.valueQuantity.value))
        else:
            values.append(observation.valueQuantity.value)
    return values        

def calculate_stats(patient_id, observations, low_threshold, high_threshold):
    if len(observations) == 0:
        return
    tir, tar, tbr = 0, 0, 0
    mean, std = 0, 0
    #Calculate mean & std first
    mean = round(sum(get_normalized_values(observations))/len(observations), 2)
    deviations = [(x - mean) ** 2 for x in get_normalized_values(observations)]
    variance = sum(deviations) / len(observations)
    std = round(math.sqrt(variance), 2)
    #Calculate TIR, TAR, TBR
    tar = round((len([value for value in get_normalized_values(observations) if value > high_threshold]) / len(observations)) * 100)
    tbr = round((len([value for value in get_normalized_values(observations) if value < low_threshold]) / len(observations)) * 100)
    tir = 100 - tar - tbr
    #Generate patient file
    generate_patient_file(patient_id, tir, tar, tbr, mean, std)


if __name__ == "__main__":
    patient_id = '17cb2a283ed-301ac2df-6b2b-49dc-87e5-27aa2efece9d'
    days_back = 14
    high_threshold = 8.3
    low_threshold = 4

    relevant_observations = []
    observations = o.Observation.where(struct={'code': 'http://loinc.org|14745-4', 'subject': f'Patient/{patient_id}'}).perform_resources(smart)
    for observation in observations:
        if datetime_in_range(datetime.now(timezone.utc) + timedelta(days=-days_back), datetime.now(timezone.utc), datetime.fromisoformat(observation.effectiveDateTime.isostring)):
            relevant_observations.append(observation)
    calculate_stats(patient_id, relevant_observations, low_threshold, high_threshold)