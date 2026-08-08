import { randomUUID } from "node:crypto";

import { mqttPassword, mqttTls, positiveInteger, required } from "./env.js";
import { probe } from "./mqtt-tracer.js";

const result = await probe({
	host: required("PAPERBRIDGE_MQTT_HOST"),
	port: positiveInteger("PAPERBRIDGE_MQTT_PORT", 1883),
	username: required("PAPERBRIDGE_MQTT_USERNAME"),
	password: mqttPassword(),
	deviceId: required("PAPERBRIDGE_DEVICE_ID"),
	clientId:
		process.env.PAPERBRIDGE_MQTT_CLIENT_ID ??
		`paperbridge-probe-${randomUUID()}`,
	timeoutMs: positiveInteger("PAPERBRIDGE_MQTT_TIMEOUT_MS", 5000),
	tls: mqttTls(),
});
process.stdout.write(`${JSON.stringify(result)}\n`);
