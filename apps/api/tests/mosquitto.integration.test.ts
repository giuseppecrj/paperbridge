import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import mqtt from "mqtt";

import { topics } from "../src/mqtt-tracer.js";
import {
	connectMqtt,
	mosquittoAvailable,
	startMosquitto,
} from "./support/mosquitto.js";

const apiRoot = fileURLToPath(new URL("..", import.meta.url));

test("Mosquitto rejects anonymous probes and returns one authenticated response", {
	skip: !mosquittoAvailable,
}, async (t) => {
	const broker = await startMosquitto();
	const { port, username, password } = broker;
	t.after(() => broker.process.kill());
	const anonymous = mqtt.connect({
		host: "127.0.0.1",
		port,
		protocol: "mqtt",
		reconnectPeriod: 0,
	});
	const authError = await new Promise<Error>((resolve) =>
		anonymous.once("error", resolve),
	);
	assert.match(authError.message, /not authorized/i);
	anonymous.end(true);

	const device = await connectMqtt({
		host: "127.0.0.1",
		port,
		protocol: "mqtt",
		protocolVersion: 4,
		clientId: "paperbridge-device-test",
		username,
		password,
		reconnectPeriod: 0,
	});
	t.after(() => device.end(true));
	const deviceTopics = topics(username);
	await new Promise<void>((resolve, reject) => {
		device.subscribe(deviceTopics.jobs, { qos: 1 }, (error) =>
			error ? reject(error) : resolve(),
		);
	});
	device.on("message", (_topic, payload) => {
		const message = JSON.parse(payload.toString("utf8"));
		device.publish(
			deviceTopics.status,
			JSON.stringify({
				schema_version: 1,
				kind: "mqtt_probe_status",
				probe_id: message.probe_id,
				device_id: username,
				status: "ok",
				ts_ms: 123,
			}),
			{ qos: 1, retain: false },
		);
	});

	const secretRoot = mkdtempSync(join(tmpdir(), "paperbridge-secret-"));
	const passwordFile = join(secretRoot, "mqtt-password");
	writeFileSync(passwordFile, password);
	t.after(() => rmSync(secretRoot, { recursive: true }));
	const env: NodeJS.ProcessEnv = {
		...process.env,
		PAPERBRIDGE_MQTT_HOST: "127.0.0.1",
		PAPERBRIDGE_MQTT_PORT: String(port),
		PAPERBRIDGE_MQTT_USERNAME: username,
		PAPERBRIDGE_DEVICE_ID: username,
		PAPERBRIDGE_MQTT_CLIENT_ID: "paperbridge-host-test",
		PAPERBRIDGE_MQTT_TIMEOUT_MS: "1000",
		PAPERBRIDGE_MQTT_TLS_ENABLED: "false",
		PAPERBRIDGE_MQTT_PASSWORD_FILE: passwordFile,
	};
	delete env.PAPERBRIDGE_MQTT_PASSWORD;
	const probe = spawn(process.execPath, ["--import", "tsx", "src/main.ts"], {
		cwd: apiRoot,
		env,
		stdio: ["ignore", "pipe", "pipe"],
	});
	t.after(() => {
		if (probe.exitCode === null && probe.signalCode === null)
			probe.kill("SIGKILL");
	});
	let stdout = "";
	let stderr = "";
	probe.stdout.on("data", (chunk) => {
		stdout += chunk;
	});
	probe.stderr.on("data", (chunk) => {
		stderr += chunk;
	});
	const [exitCode] = await once(probe, "exit");
	assert.equal(exitCode, 0, stderr);
	assert.doesNotMatch(`${stdout}\n${stderr}`, /test-password/);
	assert.equal(stderr.includes(passwordFile), false);
	const result = JSON.parse(stdout);
	assert.equal(result.status, "ok");
	assert.equal(result.device_id, username);
});
