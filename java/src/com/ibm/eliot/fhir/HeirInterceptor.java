package com.ibm.eliot.fhir;

import java.io.StringWriter;

import com.github.wnameless.json.flattener.JsonFlattener;

import com.ibm.fhir.model.format.Format;
import com.ibm.fhir.model.generator.FHIRGenerator;
import com.ibm.fhir.model.generator.exception.FHIRGeneratorException;
import com.ibm.fhir.model.resource.Resource;

import com.ibm.fhir.persistence.interceptor.FHIRPersistenceEvent;
import com.ibm.fhir.persistence.interceptor.FHIRPersistenceInterceptor;
import com.ibm.fhir.persistence.interceptor.FHIRPersistenceInterceptorException;

public class HeirInterceptor implements FHIRPersistenceInterceptor {
	
	static String defaultKafkaTopic = "fhir-wp2";
	static String defaultKafkaServer = "localhost:9092";

	public void beforeCreate(FHIRPersistenceEvent event) throws FHIRPersistenceInterceptorException {
		Resource resource = event.getFhirResource();
		System.out.println("Inside interceptor! Resource = " + resource.getClass().getName());
		
		String jsonStr = resourcetoJSON(resource);
		writeKafka(jsonStr);
	}

	public static String resourcetoJSON(Resource resource) {
		StringWriter outputWriter = new StringWriter();
		try {
			FHIRGenerator.generator(Format.JSON).generate(resource, outputWriter);
		} catch (FHIRGeneratorException e) {
			e.printStackTrace();
		}
		String singleJsonResource = outputWriter.toString();
		return (flattenAndClean(singleJsonResource));
	}
	
	public static void writeKafka(String jsonStr) {
		String envKafkaServer = System.getenv("HEIR_KAFKA_SERVER"); 
		String envKafkaTopic  = System.getenv("HEIR_KAFKA_TOPIC");
		String KAFKA_SERVER = envKafkaServer!= null ? envKafkaServer  : defaultKafkaServer;
		String KAFKA_TOPIC  = envKafkaTopic != null ? envKafkaTopic   : defaultKafkaTopic;
		
		System.out.println("In writeKafka: about to write to Kafka queue. \n"+jsonStr);
		KafkaUtils kafkaObject = new KafkaUtils(KAFKA_SERVER, KAFKA_TOPIC);
		kafkaObject.sendMessage(jsonStr);
	}

	public static String flattenAndClean(String jInput) {
		String flatJson = new JsonFlattener(jInput).withSeparator('_').flatten();
		System.out.println("-> flattening: flatJson =  " + flatJson + " flatJson = " + flatJson);
		return (flatJson);
	}
}
