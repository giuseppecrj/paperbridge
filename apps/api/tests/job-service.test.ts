import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { readFileSync } from "node:fs";
import test from "node:test";

import type { JobResult, PrintJob } from "@paperbridge/protocol";

import { JobSubmissionService, SubmissionError } from "../src/job-service.js";
import type { ImageDecoder } from "../src/image-preparer.js";

function fixture(name: string): unknown {
	return JSON.parse(
		readFileSync(
			new URL(
				`../../../packages/protocol/fixtures/print-job-v1/${name}`,
				import.meta.url,
			),
			"utf8",
		),
	);
}

const delivered: JobResult = {
	schema_version: "1",
	kind: "job_result",
	job_id: "job-hello-001",
	device_id: "paperbridge-dev-001",
	status: "delivered_to_printer",
	bytes_sent: 28,
};

test("validates and submits one configured device job", async () => {
	const calls: Array<[PrintJob, string]> = [];
	const service = new JobSubmissionService("paperbridge-dev-001", {
		submit: async (job, payload) => {
			calls.push([job, payload]);
			return delivered;
		},
	});

	assert.deepEqual(
		await service.submit(fixture("valid-text-feed.json")),
		delivered,
	);
	assert.equal(calls.length, 1);
	assert.equal(calls[0]?.[0].job_id, "job-hello-001");
	assert.equal(JSON.parse(calls[0]?.[1] ?? "{}").job_id, "job-hello-001");
});

test("prepares image sources before MQTT publication", async () => {
	const calls: Array<[PrintJob, string]> = [];
	const decoder: ImageDecoder = {
		decode: async () => ({
			width: 8,
			height: 1,
			pixels: Uint8Array.from([0, 255, 0, 255, 0, 255, 0, 255]),
		}),
	};
	const service = new JobSubmissionService(
		"paperbridge-dev-001",
		{
			submit: async (job, payload) => {
				calls.push([job, payload]);
				return delivered;
			},
		},
		decoder,
	);

	await service.submit({
		schema_version: "1",
		job_id: "job-image-001",
		device_id: "paperbridge-dev-001",
		created_at: "2026-08-03T00:00:00Z",
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
	});

	assert.deepEqual(calls[0]?.[0].content.blocks, [
		{ type: "raster", width: 8, height: 1, data_base64: "qg==" },
	]);
	assert.deepEqual(JSON.parse(calls[0]?.[1] ?? "{}"), calls[0]?.[0]);
});

test("rejects an image source before publishing when MIME and bytes disagree", async () => {
	let calls = 0;
	const service = new JobSubmissionService("paperbridge-dev-001", {
		submit: async () => {
			calls += 1;
			return delivered;
		},
	});
	await assert.rejects(
		service.submit({
			schema_version: "1",
			job_id: "job-image-invalid-001",
			device_id: "paperbridge-dev-001",
			created_at: "2026-08-03T00:00:00Z",
			content: {
				kind: "receipt",
				blocks: [
					{
						type: "image",
						mime_type: "image/jpeg",
						data_base64: "iVBORw0KGgo=",
					},
				],
			},
		}),
		(error: unknown) =>
			error instanceof SubmissionError &&
			error.errorCode === "INVALID_PRINT_JOB",
	);
	assert.equal(calls, 0);
});

test("rejects schema-invalid and wrong-device jobs before publishing", async () => {
	let calls = 0;
	const service = new JobSubmissionService("paperbridge-dev-001", {
		submit: async () => {
			calls += 1;
			return delivered;
		},
	});

	await assert.rejects(
		service.submit(fixture("invalid-fractional-feed.json")),
		(error: unknown) =>
			error instanceof SubmissionError &&
			error.statusCode === 400 &&
			error.errorCode === "INVALID_PRINT_JOB",
	);
	const wrongDevice = {
		...(fixture("valid-text-feed.json") as Record<string, unknown>),
		device_id: "other-device",
	};
	await assert.rejects(
		service.submit(wrongDevice),
		(error: unknown) =>
			error instanceof SubmissionError &&
			error.statusCode === 422 &&
			error.errorCode === "WRONG_DEVICE",
	);
	assert.equal(calls, 0);
});

test("rejects schema-valid rasters over the MQTT transport limit", async () => {
	const service = new JobSubmissionService("paperbridge-dev-001", {
		submit: async () => delivered,
	});
	const raster = {
		type: "raster",
		width: 576,
		height: 576,
		data_base64: Buffer.alloc(41_472).toString("base64"),
	};

	await assert.rejects(
		service.submit({
			schema_version: "1",
			job_id: "job-too-large",
			device_id: "paperbridge-dev-001",
			created_at: "2026-08-05T00:00:00Z",
			content: { kind: "receipt", blocks: [raster, raster] },
		}),
		(error: unknown) =>
			error instanceof SubmissionError &&
			error.statusCode === 413 &&
			error.errorCode === "PAYLOAD_TOO_LARGE",
	);
});

test("does not expose a client cut authorization field", async () => {
	const service = new JobSubmissionService("paperbridge-dev-001", {
		submit: async () => delivered,
	});
	const job = fixture("valid-text-feed.json") as Record<string, unknown>;

	await assert.rejects(
		service.submit({ ...job, allow_cut: true }),
		(error: unknown) =>
			error instanceof SubmissionError &&
			error.errorCode === "INVALID_PRINT_JOB",
	);
});
