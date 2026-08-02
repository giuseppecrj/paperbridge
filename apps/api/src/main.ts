import { randomUUID } from "node:crypto";

import { probe } from "./mqtt-tracer.js";

function required(name: string): string {
	const value = process.env[name];
	if (!value) throw new Error(`${name} is required`);
	return value;
}

function positiveInteger(name: string, fallback: number): number {
	const value = process.env[name];
	if (value === undefined) return fallback;
	const parsed = Number(value);
	if (!Number.isSafeInteger(parsed) || parsed <= 0)
		throw new Error(`${name} must be a positive integer`);
	return parsed;
}

const result = await probe({
	host: required("PAPERBRIDGE_MQTT_HOST"),
	port: positiveInteger("PAPERBRIDGE_MQTT_PORT", 1883),
	username: required("PAPERBRIDGE_MQTT_USERNAME"),
	password: required("PAPERBRIDGE_MQTT_PASSWORD"),
	deviceId: required("PAPERBRIDGE_DEVICE_ID"),
	clientId:
		process.env.PAPERBRIDGE_MQTT_CLIENT_ID ??
		`paperbridge-probe-${randomUUID()}`,
	timeoutMs: positiveInteger("PAPERBRIDGE_MQTT_TIMEOUT_MS", 5000),
});
console.log(JSON.stringify(result));
