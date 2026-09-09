import { randomUUID } from "node:crypto";

import { createApiServer } from "./api-server.js";
import {
	apiAccessPolicy,
	mqttPassword,
	mqttTls,
	positiveInteger,
	required,
} from "./env.js";
import {
	JobSubmissionService,
	type JobSubmissionOptions,
} from "./job-service.js";
import { createMcpEndpoint } from "./mcp-server.js";
import { MqttJobClient } from "./mqtt-job-client.js";

const host = process.env.PAPERBRIDGE_API_HOST ?? "127.0.0.1";
const port = positiveInteger("PAPERBRIDGE_API_PORT", 3000);
const deviceId = required("PAPERBRIDGE_DEVICE_ID");
const broker = new MqttJobClient({
	host: required("PAPERBRIDGE_MQTT_HOST"),
	port: positiveInteger("PAPERBRIDGE_MQTT_PORT", 1883),
	username: required("PAPERBRIDGE_MQTT_USERNAME"),
	password: mqttPassword(),
	deviceId,
	clientId:
		process.env.PAPERBRIDGE_MQTT_CLIENT_ID ?? `paperbridge-api-${randomUUID()}`,
	timeoutMs: positiveInteger("PAPERBRIDGE_JOB_RESULT_TIMEOUT_MS", 15_000),
	tls: mqttTls(),
});
const brokerReady = await broker.waitUntilReady(1000);
if (!brokerReady) {
	process.stderr.write(
		"MQTT broker unavailable; API will return 503 until connected\n",
	);
}
const jobs = new JobSubmissionService(deviceId, broker);
const submitJob = (value: unknown, options: JobSubmissionOptions = {}) =>
	jobs.submit(value, options);
const accessPolicy = apiAccessPolicy();
const mcp = createMcpEndpoint({
	deviceId,
	submitJob,
	accessPolicy,
});
const server = createApiServer({
	submitJob,
	mcp,
	accessPolicy,
	isReady: () => broker.isReady() && !jobs.isDraining(),
});
await new Promise<void>((resolve, reject) => {
	server.once("error", reject);
	server.listen(port, host, resolve);
});
let shutdownPromise: Promise<void> | undefined;
function shutdown(): Promise<void> {
	shutdownPromise ??= (async () => {
		await jobs.drain();
		await mcp.close();
		broker.close();
		await new Promise<void>((resolve, reject) => {
			server.close((error) => (error ? reject(error) : resolve()));
		});
	})();
	return shutdownPromise;
}
function handleShutdown(): void {
	void shutdown().catch((error: unknown) => {
		process.stderr.write(
			`Shutdown failed: ${error instanceof Error ? error.message : "unknown error"}\n`,
		);
		process.exitCode = 1;
	});
}
process.once("SIGINT", handleShutdown);
process.once("SIGTERM", handleShutdown);
