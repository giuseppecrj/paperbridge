import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
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
		"valid-styled-text.json",
		"valid-qr.json",
		"valid-qr-sized.json",
		"valid-image-png-source.json",
		"valid-image-jpeg-source.json",
		"valid-image-rich-receipt.json",
		"valid-rich-receipt.json",
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
		"invalid-qr-control-data.json",
		"invalid-qr-oversized.json",
		"invalid-oversized-text.json",
		"invalid-style-alignment.json",
		"invalid-style-multiplier.json",
		"invalid-copies.json",
		"invalid-expires-at.json",
		"invalid-empty-text.json",
		"invalid-fractional-feed.json",
	]) {
		assert.throws(() => parsePrintJob(jsonFixture("print-job-v1", name)));
	}
});

test("accepts a bounded QR module size", () => {
	const job = parsePrintJob({
		schema_version: "1",
		job_id: "job-qr-size-001",
		device_id: "paperbridge-dev-001",
		created_at: "2026-08-02T00:00:00Z",
		content: {
			kind: "receipt",
			blocks: [{ type: "qr", data: "https://example.com", module_size: 8 }],
		},
	});
	assert.equal(job.content.blocks[0].type, "qr");
	if (job.content.blocks[0].type === "qr") {
		assert.equal(job.content.blocks[0].module_size, 8);
	}
	assert.throws(() =>
		parsePrintJob({
			schema_version: "1",
			job_id: "job-qr-size-invalid",
			device_id: "paperbridge-dev-001",
			created_at: "2026-08-02T00:00:00Z",
			content: {
				kind: "receipt",
				blocks: [{ type: "qr", data: "https://example.com", module_size: 9 }],
			},
		}),
	);
});

test("distinguishes image sources from bounded device rasters", () => {
	const metadata = {
		schema_version: "1",
		job_id: "job-image-001",
		device_id: "paperbridge-dev-001",
		created_at: "2026-08-03T00:00:00Z",
	};
	assert.equal(
		parsePrintJob({
			...metadata,
			content: {
				kind: "receipt",
				blocks: [
					{
						type: "image",
						mime_type: "image/png",
						data_base64: "iVBORw0KGgo=",
					},
				],
			},
		}).content.blocks[0]?.type,
		"image",
	);
	assert.equal(
		parsePrintJob({
			...metadata,
			content: {
				kind: "receipt",
				blocks: [{ type: "raster", width: 8, height: 1, data_base64: "qg==" }],
			},
		}).content.blocks[0]?.type,
		"raster",
	);
	assert.throws(() =>
		parsePrintJob({
			...metadata,
			content: {
				kind: "receipt",
				blocks: [
					{
						type: "image",
						mime_type: "image/gif",
						data_base64: "iVBORw0KGgo=",
					},
				],
			},
		}),
	);
	assert.throws(() =>
		parsePrintJob({
			...metadata,
			content: {
				kind: "receipt",
				blocks: [{ type: "raster", width: 8, height: 2, data_base64: "AA==" }],
			},
		}),
	);
});

test("keeps the representative rich receipt below the MQTT limit", () => {
	const rich = parsePrintJob(
		jsonFixture("print-job-v1", "valid-rich-receipt.json"),
	);
	assert.equal(JSON.stringify(rich).length, 811);
	assert.doesNotThrow(() => encodePrintJob(rich));
});

test("fits one maximum raster in a bounded MQTT job", () => {
	assert.equal(MQTT_JOB_MAX_BYTES, 65_536);
	const raster = {
		type: "raster",
		width: 576,
		height: 576,
		data_base64: Buffer.alloc(41_472).toString("base64"),
	};
	const metadata = {
		schema_version: "1",
		job_id: "job-raster-maximum",
		device_id: "paperbridge-dev-001",
		created_at: "2026-08-05T00:00:00Z",
	};
	assert.doesNotThrow(() =>
		encodePrintJob(
			parsePrintJob({
				...metadata,
				content: { kind: "receipt", blocks: [raster] },
			}),
		),
	);
	assert.throws(
		() =>
			encodePrintJob(
				parsePrintJob({
					...metadata,
					content: { kind: "receipt", blocks: [raster, raster] },
				}),
			),
		/exceeds 65536 bytes/,
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

test("accepts delivery results up to the rendered-output bound", () => {
	assert.equal(
		parseJobResult({
			schema_version: "1",
			kind: "job_result",
			job_id: "job-raster-maximum",
			device_id: "paperbridge-dev-001",
			status: "delivered_to_printer",
			bytes_sent: 41_482,
		}).bytes_sent,
		41_482,
	);
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
