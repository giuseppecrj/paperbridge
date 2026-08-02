import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import type { JobResult, PrintJob } from "@paperbridge/protocol";

import { JobSubmissionService, SubmissionError } from "../src/job-service.js";

function fixture(name: string): unknown {
	return JSON.parse(
		readFileSync(
			new URL(`../../../packages/protocol/fixtures/print-job-v1/${name}`, import.meta.url),
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

	assert.deepEqual(await service.submit(fixture("valid-text-feed.json")), delivered);
	assert.equal(calls.length, 1);
	assert.equal(calls[0]?.[0].job_id, "job-hello-001");
	assert.equal(JSON.parse(calls[0]?.[1] ?? "{}").job_id, "job-hello-001");
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

test("rejects a schema-valid job over the MQTT transport limit", async () => {
	const service = new JobSubmissionService("paperbridge-dev-001", {
		submit: async () => delivered,
	});

	await assert.rejects(
		service.submit(fixture("schema-valid-over-mqtt-limit.json")),
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
			error instanceof SubmissionError && error.errorCode === "INVALID_PRINT_JOB",
	);
});
