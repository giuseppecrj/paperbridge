import { readFileSync } from "node:fs";

export function required(name: string): string {
	const value = process.env[name];
	if (!value) throw new Error(`${name} is required`);
	return value;
}

export function positiveInteger(name: string, fallback: number): number {
	const value = process.env[name];
	if (value === undefined) return fallback;
	const parsed = Number(value);
	if (!Number.isSafeInteger(parsed) || parsed <= 0) {
		throw new Error(`${name} must be a positive integer`);
	}
	return parsed;
}

export function mqttTls() {
	const enabled = process.env.PAPERBRIDGE_MQTT_TLS_ENABLED;
	if (enabled === undefined || enabled === "false") return undefined;
	if (enabled !== "true") {
		throw new Error("PAPERBRIDGE_MQTT_TLS_ENABLED must be true or false");
	}
	const ca = readFileSync(required("PAPERBRIDGE_MQTT_TLS_CA_CERTIFICATE_FILE"));
	if (ca.length === 0) {
		throw new Error(
			"PAPERBRIDGE_MQTT_TLS_CA_CERTIFICATE_FILE must not be empty",
		);
	}
	return {
		ca,
		servername: required("PAPERBRIDGE_MQTT_TLS_SERVER_HOSTNAME"),
	};
}
