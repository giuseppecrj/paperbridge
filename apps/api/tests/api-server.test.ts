import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { readFileSync } from "node:fs";
import { request as httpRequest, type Server } from "node:http";
import { connect } from "node:net";
import test from "node:test";

import { MQTT_JOB_MAX_BYTES, type JobResult } from "@paperbridge/protocol";

import { API_JOB_MAX_BYTES, createApiServer } from "../src/api-server.js";
import { JobSubmissionService, SubmissionError } from "../src/job-service.js";

async function listen(server: Server): Promise<string> {
	await new Promise<void>((resolve, reject) => {
		server.once("error", reject);
		server.listen(0, "127.0.0.1", resolve);
	});
	const address = server.address();
	assert(address && typeof address !== "string");
	return `http://127.0.0.1:${address.port}`;
}

const delivered: JobResult = {
	schema_version: "1",
	kind: "job_result",
	job_id: "job-hello-001",
	device_id: "paperbridge-dev-001",
	status: "delivered_to_printer",
	bytes_sent: 28,
};

test("health is live while readiness follows application MQTT state", async (t) => {
	let ready = false;
	const server = createApiServer({
		submitJob: async () => delivered,
		isReady: () => ready,
	});
	t.after(() => server.close());
	const baseUrl = await listen(server);

	const health = await fetch(`${baseUrl}/health`);
	assert.equal(health.status, 200);
	assert.deepEqual(await health.json(), { status: "ok" });

	const unavailable = await fetch(`${baseUrl}/ready`);
	assert.equal(unavailable.status, 503);
	assert.deepEqual(await unavailable.json(), { status: "not_ready" });

	ready = true;
	const available = await fetch(`${baseUrl}/ready`);
	assert.equal(available.status, 200);
	assert.deepEqual(await available.json(), { status: "ready" });
});

test("POST /api/jobs returns the correlated terminal result", async (t) => {
	let submitted: unknown;
	const server = createApiServer({
		submitJob: async (value) => {
			submitted = value;
			return delivered;
		},
	});
	t.after(() => server.close());
	const baseUrl = await listen(server);
	const job = {
		schema_version: "1",
		job_id: "job-hello-001",
		device_id: "paperbridge-dev-001",
		created_at: "2026-08-02T00:00:00Z",
		content: { kind: "receipt", blocks: [{ type: "text", text: "Hello" }] },
	};

	const response = await fetch(`${baseUrl}/api/jobs`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify(job),
	});

	assert.equal(response.status, 200);
	assert.deepEqual(await response.json(), delivered);
	assert.deepEqual(submitted, job);
});

test("accepts a source body larger than the prepared MQTT limit", async (t) => {
	let submitted = false;
	const server = createApiServer({
		submitJob: async () => {
			submitted = true;
			return delivered;
		},
	});
	t.after(() => server.close());
	const baseUrl = await listen(server);
	const response = await fetch(`${baseUrl}/api/jobs`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify({ source: "x".repeat(MQTT_JOB_MAX_BYTES) }),
	});
	assert.equal(response.status, 200);
	assert.equal(submitted, true);
});

test("rejects a body over the source-image limit before submission", async (t) => {
	let submissions = 0;
	const server = createApiServer({
		submitJob: async () => {
			submissions += 1;
			return delivered;
		},
	});
	t.after(() => server.close());
	const baseUrl = await listen(server);
	const response = await fetch(`${baseUrl}/api/jobs`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: "x".repeat(API_JOB_MAX_BYTES + 1),
	});
	assert.equal(response.status, 413);
	assert.equal(submissions, 0);
});

test("rejects a configured oversized body before parsing or submission", async (t) => {
	let submissions = 0;
	const server = createApiServer({
		maxBodyBytes: 1_024,
		submitJob: async () => {
			submissions += 1;
			return delivered;
		},
	});
	t.after(() => server.close());
	const baseUrl = await listen(server);

	const overLimit = Buffer.from(`{"value":"${"x".repeat(1_013)}"}`);
	assert.equal(overLimit.byteLength, 1_025);
	const response = await fetch(`${baseUrl}/api/jobs`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: new Uint8Array(overLimit),
	});

	assert.equal(response.status, 413);
	assert.deepEqual(await response.json(), {
		status: "rejected",
		error_code: "PAYLOAD_TOO_LARGE",
	});
	assert.equal(submissions, 0);
});

test("maps duplicate, rejection, and delivery failure honestly", async (t) => {
	const results: JobResult[] = [
		{
			schema_version: "1",
			kind: "job_result",
			job_id: "job-duplicate",
			device_id: "paperbridge-dev-001",
			status: "duplicate",
			error_code: "DUPLICATE_JOB",
		},
		{
			schema_version: "1",
			kind: "job_result",
			job_id: "job-rejected",
			device_id: "paperbridge-dev-001",
			status: "rejected",
			error_code: "UNAUTHORIZED_CUT",
		},
		{
			schema_version: "1",
			kind: "job_result",
			job_id: "job-partial",
			device_id: "paperbridge-dev-001",
			status: "failed",
			error_code: "PRINTER_CONNECTION_RESET",
			bytes_sent: 2,
		},
	];
	const server = createApiServer({
		submitJob: async () => results.shift() as JobResult,
	});
	t.after(() => server.close());
	const baseUrl = await listen(server);

	for (const expectedStatus of [409, 422, 502]) {
		const response = await fetch(`${baseUrl}/api/jobs`, {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: "{}",
		});
		assert.equal(response.status, expectedStatus);
	}
});

test("maps broker, duplicate, and timeout failures without inventing delivery", async (t) => {
	const errors = [
		new SubmissionError(
			503,
			"BROKER_UNAVAILABLE",
			"failed",
			"job-1",
			"device-1",
		),
		new SubmissionError(
			409,
			"JOB_ALREADY_PENDING",
			"rejected",
			"job-1",
			"device-1",
		),
		new SubmissionError(
			504,
			"DEVICE_RESULT_TIMEOUT",
			"unknown",
			"job-1",
			"device-1",
		),
	];
	const server = createApiServer({
		submitJob: async () => {
			throw errors.shift();
		},
	});
	t.after(() => server.close());
	const baseUrl = await listen(server);

	for (const [statusCode, responseStatus, errorCode] of [
		[503, "failed", "BROKER_UNAVAILABLE"],
		[409, "rejected", "JOB_ALREADY_PENDING"],
		[504, "unknown", "DEVICE_RESULT_TIMEOUT"],
	] as const) {
		const response = await fetch(`${baseUrl}/api/jobs`, {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: "{}",
		});
		assert.equal(response.status, statusCode);
		assert.deepEqual(await response.json(), {
			job_id: "job-1",
			device_id: "device-1",
			status: responseStatus,
			error_code: errorCode,
		});
	}
});

test("public endpoint rejects schema-invalid and wrong-device jobs before MQTT", async (t) => {
	let publishes = 0;
	const jobs = new JobSubmissionService("paperbridge-dev-001", {
		submit: async () => {
			publishes += 1;
			return delivered;
		},
	});
	const server = createApiServer({ submitJob: (value) => jobs.submit(value) });
	t.after(() => server.close());
	const baseUrl = await listen(server);
	const invalid = readFileSync(
		new URL(
			"../../../packages/protocol/fixtures/print-job-v1/invalid-fractional-feed.json",
			import.meta.url,
		),
		"utf8",
	);
	const valid = JSON.parse(
		readFileSync(
			new URL(
				"../../../packages/protocol/fixtures/print-job-v1/valid-text-feed.json",
				import.meta.url,
			),
			"utf8",
		),
	) as Record<string, unknown>;

	for (const [body, statusCode, errorCode] of [
		[invalid, 400, "INVALID_PRINT_JOB"],
		[
			JSON.stringify({ ...valid, device_id: "other-device" }),
			422,
			"WRONG_DEVICE",
		],
	] as const) {
		const response = await fetch(`${baseUrl}/api/jobs`, {
			method: "POST",
			headers: { "content-type": "application/json" },
			body,
		});
		assert.equal(response.status, statusCode);
		assert.equal(
			((await response.json()) as { error_code: string }).error_code,
			errorCode,
		);
	}
	assert.equal(publishes, 0);
});

test("rejects malformed JSON distinctly", async (t) => {
	const server = createApiServer({ submitJob: async () => delivered });
	t.after(() => server.close());
	const baseUrl = await listen(server);

	const response = await fetch(`${baseUrl}/api/jobs`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: "{",
	});

	assert.equal(response.status, 400);
	assert.deepEqual(await response.json(), {
		status: "rejected",
		error_code: "MALFORMED_JSON",
	});
});

test("REST rejects untrusted Host and Origin before publishing", async (t) => {
	let publishes = 0;
	const jobs = new JobSubmissionService("paperbridge-dev-001", {
		submit: async () => {
			publishes += 1;
			return delivered;
		},
	});
	const server = createApiServer({ submitJob: (value) => jobs.submit(value) });
	t.after(() => server.close());
	const baseUrl = await listen(server);
	const body = readFileSync(
		new URL(
			"../../../packages/protocol/fixtures/print-job-v1/valid-text-feed.json",
			import.meta.url,
		),
		"utf8",
	);
	for (const headers of [
		{ host: "attacker.example" },
		{ origin: "https://attacker.example" },
		{ origin: "null" },
		{ origin: "ftp://localhost" },
		{ origin: "http://localhost/path" },
	] as Record<string, string>[]) {
		const status = await new Promise<number>((resolve, reject) => {
			const request = httpRequest(`${baseUrl}/api/jobs`, {
				method: "POST",
				headers: { "content-type": "application/json", ...headers },
			}, response => {
				response.resume();
				response.once("end", () => resolve(response.statusCode ?? 0));
			});
			request.once("error", reject);
			request.end(body);
		});
		assert.equal(status, 403);
	}
	assert.equal(publishes, 0);
});

test("REST accepts configured proxy and loopback callers, with or without Origin", async (t) => {
	let submissions = 0;
	const server = createApiServer({
		submitJob: async () => {
			submissions += 1;
			return delivered;
		},
		accessPolicy: {
			allowedHostnames: ["127.0.0.1", "paperbridge.example"],
			allowedOrigins: ["https://paperbridge.example"],
		},
	});
	t.after(() => server.close());
	const baseUrl = await listen(server);
	for (const headers of [
		{ host: "paperbridge.example" },
		{ host: "paperbridge.example", origin: "https://paperbridge.example" },
		{ host: "127.0.0.1", origin: "http://localhost:3000" },
		{ host: "127.0.0.1", origin: "https://[::1]:3000" },
	] as Record<string, string>[]) {
		const status = await new Promise<number>((resolve, reject) => {
			const request = httpRequest(`${baseUrl}/api/jobs`, {
				method: "POST",
				headers: { "content-type": "application/json", ...headers },
			}, (response) => {
				response.resume();
				response.once("end", () => resolve(response.statusCode ?? 0));
			});
			request.once("error", reject);
			request.end("{}");
		});
		assert.equal(status, 200);
	}
	assert.equal(submissions, 4);
});

test("REST rejects a missing Host header before submission", async (t) => {
	let submissions = 0;
	const server = createApiServer({
		submitJob: async () => {
			submissions += 1;
			return delivered;
		},
	});
	t.after(() => server.close());
	const baseUrl = await listen(server);
	const status = await new Promise<number>((resolve, reject) => {
		const socket = connect(Number(new URL(baseUrl).port), "127.0.0.1", () => {
			socket.write("POST /api/jobs HTTP/1.0\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}");
		});
		let response = "";
		socket.on("data", (chunk) => { response += chunk; });
		socket.once("end", () => resolve(Number(response.split(" ")[1])));
		socket.once("error", reject);
	});
	assert.equal(status, 403);
	assert.equal(submissions, 0);
});
