import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
	MQTT_JOB_MAX_BYTES,
	encodePrintJob,
	jobTopics,
	parseJobResult,
	parsePrintJob,
} from "../src/index.js";

function fixture(directory: string, name: string) {
	return readFileSync(
		new URL(`../fixtures/${directory}/${name}`, import.meta.url),
	);
}

function jsonFixture(directory: string, name: string): unknown {
	return JSON.parse(fixture(directory, name).toString("utf8"));
}

test("loads the authoritative print-job schema and shared fixtures", () => {
	for (const name of [
		"valid-text-feed.json",
		"valid-rule.json",
		"valid-cut.json",
	]) {
		assert.equal(
			parsePrintJob(jsonFixture("print-job-v1", name)).schema_version,
			"1",
		);
	}
	for (const name of [
		"invalid-raw-block.json",
		"invalid-control-text.json",
		"invalid-style-fields.json",
		"invalid-copies.json",
		"invalid-expires-at.json",
		"invalid-empty-text.json",
		"invalid-fractional-feed.json",
	]) {
		assert.throws(() => parsePrintJob(jsonFixture("print-job-v1", name)));
	}
});

test("keeps schema validity separate from the 1024-byte MQTT limit", () => {
	const atLimit = fixture("print-job-v1", "valid-at-mqtt-limit.json");
	const overLimit = fixture(
		"print-job-v1",
		"schema-valid-over-mqtt-limit.json",
	);
	assert.equal(atLimit.byteLength, MQTT_JOB_MAX_BYTES);
	assert.equal(overLimit.byteLength, MQTT_JOB_MAX_BYTES + 1);
	assert.doesNotThrow(() =>
		encodePrintJob(parsePrintJob(JSON.parse(atLimit.toString("utf8")))),
	);
	assert.throws(
		() => encodePrintJob(parsePrintJob(JSON.parse(overLimit.toString("utf8")))),
		/exceeds 1024 bytes/,
	);
});

test("validates every terminal job-result fixture", () => {
	for (const name of [
		"delivered.json",
		"duplicate.json",
		"rejected-validation.json",
		"transport-failure.json",
		"partial-write.json",
	]) {
		assert.equal(
			parseJobResult(jsonFixture("job-result-v1", name)).kind,
			"job_result",
		);
	}
});

test("rejects result fields that contradict the terminal status", () => {
	const delivered = jsonFixture("job-result-v1", "delivered.json") as Record<
		string,
		unknown
	>;
	assert.throws(() =>
		parseJobResult({ ...delivered, error_code: "INTERNAL_ERROR" }),
	);
	const rejected = jsonFixture(
		"job-result-v1",
		"rejected-validation.json",
	) as Record<string, unknown>;
	assert.throws(() => parseJobResult({ ...rejected, bytes_sent: 0 }));
	const duplicate = jsonFixture("job-result-v1", "duplicate.json") as Record<
		string,
		unknown
	>;
	assert.throws(() => parseJobResult({ ...duplicate, bytes_sent: 0 }));
	assert.throws(() =>
		parseJobResult({ ...duplicate, error_code: "INTERNAL_ERROR" }),
	);
});

test("uses dedicated MQTT job topics without changing the probe topics", () => {
	assert.deepEqual(jobTopics("paperbridge-dev-001"), {
		jobs: "v1/devices/paperbridge-dev-001/print-jobs",
		results: "v1/devices/paperbridge-dev-001/job-results",
	});
	assert.throws(() => jobTopics("device/other"), /safe MQTT topic segment/);
});
