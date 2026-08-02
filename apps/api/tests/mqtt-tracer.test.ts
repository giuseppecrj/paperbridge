import assert from "node:assert/strict";
import test from "node:test";

import { buildProbe, topics } from "../src/mqtt-tracer.js";

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
