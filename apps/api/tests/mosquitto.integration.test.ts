import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn, spawnSync } from "node:child_process";
import test from "node:test";

import mqtt from "mqtt";

import { probe, topics } from "../src/mqtt-tracer.js";

const mosquitto = process.env.MOSQUITTO_BIN ?? "mosquitto";
const mosquittoPasswd = process.env.MOSQUITTO_PASSWD_BIN ?? "mosquitto_passwd";
const integrationAvailable = [mosquitto, mosquittoPasswd].every(
	(command) => spawnSync(command, ["-h"], { stdio: "ignore" }).status === 0,
);

function unusedPort(): Promise<number> {
	return new Promise((resolve, reject) => {
		const server = createServer();
		server.once("error", reject);
		server.listen(0, "127.0.0.1", () => {
			const address = server.address();
			if (!address || typeof address === "string") {
				reject(new Error("could not allocate a TCP port"));
				return;
			}
			server.close((error) => (error ? reject(error) : resolve(address.port)));
		});
	});
}

function connect(options: mqtt.IClientOptions): Promise<mqtt.MqttClient> {
	const client = mqtt.connect(options);
	return new Promise((resolve, reject) => {
		const onError = (error: Error) => reject(error);
		client.once("error", onError);
		client.once("connect", () => {
			client.removeListener("error", onError);
			resolve(client);
		});
	});
}

test("Mosquitto rejects anonymous probes and returns one authenticated response", {
	skip: !integrationAvailable,
}, async (t) => {
	const root = await mkdtemp(join(tmpdir(), "paperbridge-mosquitto-"));
	const passwordFile = join(root, "passwd");
	const port = await unusedPort();
	const username = "paperbridge-dev-001";
	const password = "test-password";
	assert.equal(
		spawnSync(mosquittoPasswd, ["-b", "-c", passwordFile, username, password])
			.status,
		0,
	);
	await writeFile(
		join(root, "mosquitto.conf"),
		`listener ${port} 127.0.0.1\nallow_anonymous false\npassword_file ${passwordFile}\npersistence false\n`,
	);
	const broker = spawn(mosquitto, ["-c", join(root, "mosquitto.conf")], {
		stdio: "ignore",
	});
	t.after(() => broker.kill());

	await new Promise((resolve) => setTimeout(resolve, 50));
	const anonymous = mqtt.connect({
		host: "127.0.0.1",
		port,
		protocol: "mqtt",
		reconnectPeriod: 0,
	});
	await new Promise<void>((resolve) =>
		anonymous.once("error", () => resolve()),
	);
	anonymous.end(true);

	const device = await connect({
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

	const result = await probe({
		host: "127.0.0.1",
		port,
		username,
		password,
		deviceId: username,
		clientId: "paperbridge-host-test",
		timeoutMs: 1000,
	});

	assert.equal(result.status, "ok");
	assert.equal(result.device_id, username);
});
