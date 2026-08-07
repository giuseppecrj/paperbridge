import assert from "node:assert/strict";
import test from "node:test";

import { buildProbe, connectionOptions, topics } from "../src/mqtt-tracer.js";

test("uses certificate verification and SNI only when MQTT TLS is enabled", () => {
	const config = {
		deviceId: "paperbridge-dev-001",
		host: "abc.emqxsl.com",
		port: 8883,
		username: "device",
		password: "password",
		clientId: "probe-test",
		timeoutMs: 1000,
		tls: { ca: Buffer.from("CA"), servername: "abc.emqxsl.com" },
	};

	assert.deepEqual(connectionOptions(config), {
		host: "abc.emqxsl.com",
		port: 8883,
		protocol: "mqtts",
		protocolVersion: 4,
		clientId: "probe-test",
		username: "device",
		password: "password",
		clean: true,
		reconnectPeriod: 0,
		ca: Buffer.from("CA"),
		servername: "abc.emqxsl.com",
		rejectUnauthorized: true,
	});
	assert.equal(
		connectionOptions({ ...config, tls: undefined }).protocol,
		"mqtt",
	);
});

test("builds a bounded correlated MQTT probe on the device topics", () => {
	const probe = buildProbe(
		"paperbridge-dev-001",
		"probe-001",
		"2026-08-02T00:00:00Z",
	);

	assert.deepEqual(probe, {
		schema_version: 1,
		kind: "mqtt_probe",
		probe_id: "probe-001",
		device_id: "paperbridge-dev-001",
		created_at: "2026-08-02T00:00:00Z",
	});
	assert.deepEqual(topics("paperbridge-dev-001"), {
		jobs: "v1/devices/paperbridge-dev-001/jobs",
		status: "v1/devices/paperbridge-dev-001/status",
	});
});

test("rejects a probe with an unbounded device identifier", () => {
	assert.throws(
		() => buildProbe("x".repeat(65), "probe-001", "2026-08-02T00:00:00Z"),
		/deviceId must be 1..64 characters/,
	);
});
