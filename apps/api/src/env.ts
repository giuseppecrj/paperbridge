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

export const LOOPBACK_HOSTNAMES = ["localhost", "127.0.0.1", "[::1]"];
export const LOOPBACK_ORIGINS = [
	"http://localhost",
	"http://127.0.0.1",
	"http://[::1]",
];

function optionalBounded(name: string, maximum: number): string | undefined {
	const value = process.env[name]?.trim();
	if (!value) return undefined;
	if (value.length > maximum) {
		throw new Error(`${name} is too long`);
	}
	return value;
}

export function apiAccessPolicy() {
	const host = optionalBounded("PAPERBRIDGE_API_ALLOWED_HOST", 253);
	if (
		host &&
		(host.includes("/") || host.includes(":") || host.includes("@"))
	) {
		throw new Error("PAPERBRIDGE_API_ALLOWED_HOST must be a hostname");
	}

	const origin = optionalBounded("PAPERBRIDGE_API_ALLOWED_ORIGIN", 2048);
	if (origin) {
		let parsed: URL;
		try {
			parsed = new URL(origin);
		} catch {
			throw new Error("PAPERBRIDGE_API_ALLOWED_ORIGIN must be an HTTPS origin");
		}
		if (
			parsed.protocol !== "https:" ||
			parsed.origin !== origin ||
			parsed.username ||
			parsed.password ||
			parsed.pathname !== "/" ||
			parsed.search ||
			parsed.hash
		) {
			throw new Error("PAPERBRIDGE_API_ALLOWED_ORIGIN must be an HTTPS origin");
		}
	}

	return {
		allowedHostnames: host ? [...LOOPBACK_HOSTNAMES, host] : LOOPBACK_HOSTNAMES,
		allowedOrigins: origin ? [...LOOPBACK_ORIGINS, origin] : LOOPBACK_ORIGINS,
	};
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
