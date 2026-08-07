import assert from "node:assert/strict";
import { request as httpRequest } from "node:http";
import type { AddressInfo } from "node:net";
import test from "node:test";

import {
	Client,
	StreamableHTTPClientTransport,
} from "@modelcontextprotocol/client";
import type { JobResult } from "@paperbridge/protocol";

import { createApiServer } from "../src/api-server.js";
import { SubmissionError } from "../src/job-service.js";
import { createMcpEndpoint } from "../src/mcp-server.js";

const delivered: JobResult = {
	schema_version: "1",
	kind: "job_result",
	job_id: "job-mcp-001",
	device_id: "paperbridge-dev-001",
	status: "delivered_to_printer",
	bytes_sent: 28,
};
const content = {
	kind: "receipt",
	blocks: [{ type: "text", text: "Hello from MCP" }],
};

async function post(
	baseUrl: string,
	headers: Record<string, string>,
): Promise<number> {
	return new Promise((resolve, reject) => {
		const request = httpRequest(
			`${baseUrl}/mcp`,
			{ method: "POST", headers },
			(response) => {
				response.resume();
				response.once("end", () => resolve(response.statusCode ?? 0));
			},
		);
		request.once("error", reject);
		request.end("{}");
	});
}

async function listen(
	server: ReturnType<typeof createApiServer>,
): Promise<string> {
	await new Promise<void>((resolve, reject) => {
		server.once("error", reject);
		server.listen(0, "127.0.0.1", resolve);
	});
	const address = server.address() as AddressInfo;
	return `http://127.0.0.1:${address.port}`;
}

test("accepts the configured proxy Host and exact HTTPS Origin", async (t) => {
	const mcp = createMcpEndpoint({
		deviceId: "paperbridge-dev-001",
		submitJob: async () => delivered,
		accessPolicy: {
			allowedHostnames: [
				"localhost",
				"127.0.0.1",
				"[::1]",
				"paperbridge.example.exe.xyz",
			],
			allowedOrigins: [
				"http://localhost",
				"http://127.0.0.1",
				"http://[::1]",
				"https://paperbridge.example.exe.xyz",
			],
		},
	});
	const server = createApiServer({ submitJob: async () => delivered, mcp });
	const baseUrl = await listen(server);
	t.after(async () => {
		await mcp.close();
		await new Promise<void>((resolve) => server.close(() => resolve()));
	});

	assert.notEqual(
		await post(baseUrl, { host: "paperbridge.example.exe.xyz" }),
		403,
	);
	assert.notEqual(
		await post(baseUrl, {
			host: "paperbridge.example.exe.xyz",
			origin: "https://paperbridge.example.exe.xyz",
		}),
		403,
	);
	assert.notEqual(
		await post(baseUrl, {
			host: "127.0.0.1",
			origin: "http://localhost:3000",
		}),
		403,
	);
	assert.notEqual(
		await post(baseUrl, {
			host: "127.0.0.1",
			origin: "https://localhost:3000",
		}),
		403,
	);
	assert.equal(
		await post(baseUrl, {
			host: "paperbridge.example.exe.xyz",
			origin: "http://paperbridge.example.exe.xyz",
		}),
		403,
	);
	assert.equal(
		await post(baseUrl, {
			host: "unconfigured.example.exe.xyz",
		}),
		403,
	);
});

test("discovers and calls the print tool through the shared job service", async (t) => {
	const submissions: unknown[] = [];
	const ids = ["job-mcp-001", "job-mcp-002", "job-mcp-003"];
	const submitJob = async (value: unknown): Promise<JobResult> => {
		submissions.push(value);
		const job = value as { job_id: string; content: typeof content };
		if (job.content.blocks[0]?.text === "Duplicate") {
			return {
				schema_version: "1",
				kind: "job_result",
				job_id: job.job_id,
				device_id: "paperbridge-dev-001",
				status: "duplicate",
				error_code: "DUPLICATE_JOB",
			};
		}
		if (job.content.blocks[0]?.text === "Timeout") {
			throw new SubmissionError(
				504,
				"DEVICE_RESULT_TIMEOUT",
				"unknown",
				job.job_id,
				"paperbridge-dev-001",
			);
		}
		return delivered;
	};
	const mcp = createMcpEndpoint({
		deviceId: "paperbridge-dev-001",
		submitJob,
		createJobId: () => ids.shift() as string,
		now: () => "2026-08-02T00:00:00Z",
	});
	const server = createApiServer({ submitJob, mcp });
	const baseUrl = await listen(server);
	let client: Client | undefined;
	t.after(async () => {
		await client?.close();
		await mcp.close();
		await new Promise<void>((resolve) => server.close(() => resolve()));
	});
	assert.equal(
		await post(baseUrl, {
			"content-type": "application/json",
			host: "attacker.test",
		}),
		403,
	);
	assert.equal(
		await post(baseUrl, {
			"content-type": "application/json",
			origin: "https://attacker.test",
		}),
		403,
	);
	client = new Client(
		{ name: "paperbridge-test", version: "1.0.0" },
		{ versionNegotiation: { mode: { pin: "2026-07-28" } } },
	);
	await client.connect(
		new StreamableHTTPClientTransport(new URL(`${baseUrl}/mcp`)),
	);

	assert.deepEqual(
		(await client.listTools()).tools.map((tool) => tool.name),
		["paperbridge_print"],
	);
	const invalid = await client.callTool({
		name: "paperbridge_print",
		arguments: {
			content: {
				kind: "receipt",
				blocks: [{ type: "text", text: "invalid\ntext" }],
			},
		},
	});
	assert.equal(invalid.isError, true);
	assert.deepEqual(submissions, []);

	const result = await client.callTool({
		name: "paperbridge_print",
		arguments: { content },
	});

	assert.deepEqual(submissions, [
		{
			schema_version: "1",
			job_id: "job-mcp-001",
			device_id: "paperbridge-dev-001",
			created_at: "2026-08-02T00:00:00Z",
			content,
		},
	]);
	assert.deepEqual(result.structuredContent, delivered);

	const duplicate = await client.callTool({
		name: "paperbridge_print",
		arguments: {
			content: {
				kind: "receipt",
				blocks: [{ type: "text", text: "Duplicate" }],
			},
		},
	});
	assert.equal(duplicate.isError, true);
	assert.deepEqual(duplicate.structuredContent, {
		schema_version: "1",
		kind: "job_result",
		job_id: "job-mcp-002",
		device_id: "paperbridge-dev-001",
		status: "duplicate",
		error_code: "DUPLICATE_JOB",
	});

	const timedOut = await client.callTool({
		name: "paperbridge_print",
		arguments: {
			content: {
				kind: "receipt",
				blocks: [{ type: "text", text: "Timeout" }],
			},
		},
	});
	assert.equal(timedOut.isError, true);
	assert.deepEqual(timedOut.structuredContent, {
		job_id: "job-mcp-003",
		device_id: "paperbridge-dev-001",
		status: "unknown",
		error_code: "DEVICE_RESULT_TIMEOUT",
	});
});

test("cancellation aborts the shared application waiter", async (t) => {
	let serviceSignal: AbortSignal | undefined;
	let startedResolve: (() => void) | undefined;
	let abortedResolve: (() => void) | undefined;
	const started = new Promise<void>((resolve) => {
		startedResolve = resolve;
	});
	const aborted = new Promise<void>((resolve) => {
		abortedResolve = resolve;
	});
	const mcp = createMcpEndpoint({
		deviceId: "paperbridge-dev-001",
		createJobId: () => "job-cancelled",
		now: () => "2026-08-02T00:00:00Z",
		submitJob: async (_value, options) => {
			serviceSignal = options?.signal;
			startedResolve?.();
			return new Promise<JobResult>((_resolve, reject) => {
				serviceSignal?.addEventListener(
					"abort",
					() => {
						abortedResolve?.();
						reject(new DOMException("Request cancelled", "AbortError"));
					},
					{ once: true },
				);
			});
		},
	});
	const server = createApiServer({ submitJob: async () => delivered, mcp });
	const baseUrl = await listen(server);
	let client: Client | undefined;
	t.after(async () => {
		await client?.close();
		await mcp.close();
		await new Promise<void>((resolve) => server.close(() => resolve()));
	});
	client = new Client(
		{ name: "paperbridge-test", version: "1.0.0" },
		{ versionNegotiation: { mode: { pin: "2026-07-28" } } },
	);
	await client.connect(
		new StreamableHTTPClientTransport(new URL(`${baseUrl}/mcp`)),
	);
	const controller = new AbortController();
	const call = client.callTool(
		{ name: "paperbridge_print", arguments: { content } },
		{ signal: controller.signal },
	);
	await started;

	controller.abort();

	await assert.rejects(call);
	let timeout: ReturnType<typeof setTimeout> | undefined;
	await Promise.race([
		aborted,
		new Promise<void>((_resolve, reject) => {
			timeout = setTimeout(
				() => reject(new Error("server cancellation was not observed")),
				1000,
			);
		}),
	]);
	if (timeout) clearTimeout(timeout);
	assert.equal(serviceSignal?.aborted, true);
});
