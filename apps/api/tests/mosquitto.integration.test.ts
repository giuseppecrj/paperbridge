import assert from "node:assert/strict";
import test from "node:test";

import mqtt from "mqtt";

import { probe, topics } from "../src/mqtt-tracer.js";
import {
	connectMqtt,
	mosquittoAvailable,
	startMosquitto,
} from "./support/mosquitto.js";

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
