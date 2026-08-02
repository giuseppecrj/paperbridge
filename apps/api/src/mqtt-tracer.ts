import { randomUUID } from "node:crypto";

import mqtt from "mqtt";

export interface MqttProbe {
	schema_version: 1;
	kind: "mqtt_probe";
	probe_id: string;
	device_id: string;
	created_at: string;
}

export interface MqttProbeStatus {
	schema_version: 1;
	kind: "mqtt_probe_status";
	probe_id: string;
	device_id: string;
	status: "ok";
	ts_ms: number;
}

export interface MqttTracerConfig {
	host: string;
	port: number;
	username: string;
	password: string;
	deviceId: string;
	clientId: string;
	timeoutMs: number;
}

export function topics(deviceId: string) {
	return {
		jobs: `v1/devices/${deviceId}/jobs`,
		status: `v1/devices/${deviceId}/status`,
	};
}

function boundedText(name: string, value: string, maximum: number): void {
	if (value.length < 1 || value.length > maximum) {
		throw new Error(`${name} must be 1..${maximum} characters`);
	}
}

export function buildProbe(
	deviceId: string,
	probeId: string,
	createdAt: string,
): MqttProbe {
	boundedText("deviceId", deviceId, 64);
	boundedText("probeId", probeId, 128);
	boundedText("createdAt", createdAt, 64);
	const probe: MqttProbe = {
		schema_version: 1,
		kind: "mqtt_probe",
		probe_id: probeId,
		device_id: deviceId,
		created_at: createdAt,
	};
	if (Buffer.byteLength(JSON.stringify(probe)) > 1024) {
		throw new Error("MQTT probe exceeds 1024 bytes");
	}
	return probe;
}

function parseStatus(payload: Buffer): MqttProbeStatus | undefined {
	try {
		const value: unknown = JSON.parse(payload.toString("utf8"));
		if (
			typeof value !== "object" ||
			value === null ||
			(value as MqttProbeStatus).schema_version !== 1 ||
			(value as MqttProbeStatus).kind !== "mqtt_probe_status" ||
			(value as MqttProbeStatus).status !== "ok" ||
			typeof (value as MqttProbeStatus).probe_id !== "string" ||
			typeof (value as MqttProbeStatus).device_id !== "string" ||
			typeof (value as MqttProbeStatus).ts_ms !== "number"
		) {
			return undefined;
		}
		return value as MqttProbeStatus;
	} catch {
		return undefined;
	}
}

export function probe(config: MqttTracerConfig): Promise<MqttProbeStatus> {
	const probeId = randomUUID();
	const requested = buildProbe(
		config.deviceId,
		probeId,
		new Date().toISOString(),
	);
	const deviceTopics = topics(config.deviceId);

	return new Promise((resolve, reject) => {
		const client = mqtt.connect({
			host: config.host,
			port: config.port,
			protocol: "mqtt",
			protocolVersion: 4,
			clientId: config.clientId,
			username: config.username,
			password: config.password,
			clean: true,
			reconnectPeriod: 0,
		});
		const timeout = setTimeout(
			() => finish(new Error("MQTT probe timed out")),
			config.timeoutMs,
		);
		let settled = false;

		function finish(result: MqttProbeStatus | Error) {
			if (settled) return;
			settled = true;
			clearTimeout(timeout);
			client.end(true);
			if (result instanceof Error) reject(result);
			else resolve(result);
		}

		client.once("error", finish);
		client.once("connect", () => {
			client.subscribe(deviceTopics.status, { qos: 1 }, (error) => {
				if (error) {
					finish(error);
					return;
				}
				client.publish(
					deviceTopics.jobs,
					JSON.stringify(requested),
					{ qos: 1, retain: false },
					(publishError) => {
						if (publishError) finish(publishError);
					},
				);
			});
		});
		client.on("message", (topic, payload) => {
			if (topic !== deviceTopics.status) return;
			const status = parseStatus(payload);
			if (status?.probe_id === probeId && status.device_id === config.deviceId)
				finish(status);
		});
	});
}
