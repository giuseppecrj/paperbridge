import assert from "node:assert/strict";
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";

import {
	Client,
	StreamableHTTPClientTransport,
} from "@modelcontextprotocol/client";
import {
	jobTopics,
	type JobResult,
	type PrintJob,
} from "@paperbridge/protocol";

import {
	connectMqtt,
	mosquittoAvailable,
	startMosquitto,
} from "./support/mosquitto.js";
import { unusedPort } from "./support/unused-port.js";

const apiRoot = fileURLToPath(new URL("..", import.meta.url));
const deviceId = "paperbridge-dev-001";
const password = "test-password";

function buildProduction(): void {
	const build = spawnSync("bun", ["run", "build"], {
		cwd: apiRoot,
		encoding: "utf8",
	});
	assert.equal(build.status, 0, `${build.stdout}\n${build.stderr}`);
	assert.match(
		readFileSync(new URL("../dist/server.js", import.meta.url), "utf8"),
		/from "sharp";/,
	);
}

function startProduction(
	apiPort: number,
	mqttPort: number,
	passwordFile?: string,
) {
	const env: NodeJS.ProcessEnv = {
		...process.env,
		PAPERBRIDGE_API_HOST: "127.0.0.1",
		PAPERBRIDGE_API_PORT: String(apiPort),
		PAPERBRIDGE_DEVICE_ID: deviceId,
		PAPERBRIDGE_MQTT_HOST: "127.0.0.1",
		PAPERBRIDGE_MQTT_PORT: String(mqttPort),
		PAPERBRIDGE_MQTT_USERNAME: deviceId,
	};
	delete env.PAPERBRIDGE_MQTT_PASSWORD;
	delete env.PAPERBRIDGE_MQTT_PASSWORD_FILE;
	if (passwordFile) env.PAPERBRIDGE_MQTT_PASSWORD_FILE = passwordFile;
	else env.PAPERBRIDGE_MQTT_PASSWORD = password;
	const child = spawn(process.execPath, ["dist/server.js"], {
		cwd: apiRoot,
		env,
		stdio: ["ignore", "pipe", "pipe"],
	});
	let output = "";
	child.stdout?.on("data", (chunk) => {
		output += chunk;
	});
	child.stderr?.on("data", (chunk) => {
		output += chunk;
	});
	return { child, output: () => output };
}

async function waitForResponse(
	url: string,
	child: ChildProcess,
	output: () => string,
): Promise<Response> {
	const deadline = Date.now() + 10_000;
	while (Date.now() < deadline) {
		if (child.exitCode !== null || child.signalCode !== null) {
			throw new Error(`production server exited early\n${output()}`);
		}
		try {
			return await fetch(url);
		} catch {
			await delay(25);
		}
	}
	throw new Error(`production server did not start\n${output()}`);
}

async function stop(child: ChildProcess): Promise<void> {
	if (child.exitCode !== null || child.signalCode !== null) return;
	child.kill("SIGKILL");
	await once(child, "exit");
}

test("builds and runs the production API artifact with Node", {
	timeout: 20_000,
}, async (t) => {
	buildProduction();
	const apiPort = await unusedPort();
	const { child, output } = startProduction(apiPort, await unusedPort());
	t.after(() => stop(child));

	const baseUrl = `http://127.0.0.1:${apiPort}`;
	const health = await waitForResponse(`${baseUrl}/health`, child, output);
	assert.equal(health.status, 200);
	assert.deepEqual(await health.json(), { status: "ok" });

	const ready = await fetch(`${baseUrl}/ready`);
	assert.equal(ready.status, 503);
	assert.deepEqual(await ready.json(), { status: "not_ready" });

	const oversized = await fetch(`${baseUrl}/api/jobs`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: "x".repeat(2 * 1024 * 1024 + 4097),
	});
	assert.equal(oversized.status, 413);
	assert.deepEqual(await oversized.json(), {
		status: "rejected",
		error_code: "PAYLOAD_TOO_LARGE",
	});

	const rejectedMcp = await fetch(`${baseUrl}/mcp`, {
		method: "POST",
		headers: { origin: "https://not-paperbridge.invalid" },
		body: "{}",
	});
	assert.equal(rejectedMcp.status, 403);
});

test("prepares image fixtures through the production API and MQTT", {
	skip: !mosquittoAvailable,
	timeout: 20_000,
}, async (t) => {
	buildProduction();
	const broker = await startMosquitto();
	t.after(() => broker.process.kill());
	const topics = jobTopics(deviceId);
	const receivedJobs: PrintJob[] = [];
	const device = await connectMqtt({
		host: "127.0.0.1",
		port: broker.port,
		protocol: "mqtt",
		protocolVersion: 4,
		clientId: "paperbridge-production-bundle-device",
		username: deviceId,
		password,
		reconnectPeriod: 0,
	});
	t.after(() => device.end(true));
	await new Promise<void>((resolve, reject) => {
		device.subscribe(topics.jobs, { qos: 1 }, (error) =>
			error ? reject(error) : resolve(),
		);
	});
	device.on("message", (_topic, payload) => {
		const job = JSON.parse(payload.toString("utf8")) as PrintJob;
		receivedJobs.push(job);
		device.publish(
			topics.results,
			JSON.stringify({
				schema_version: "1",
				kind: "job_result",
				job_id: job.job_id,
				device_id: deviceId,
				status: "delivered_to_printer",
				bytes_sent: 8,
			}),
			{ qos: 1, retain: false },
		);
	});

	const secretRoot = mkdtempSync(join(tmpdir(), "paperbridge-secret-"));
	const passwordFile = join(secretRoot, "mqtt-password");
	writeFileSync(passwordFile, password);
	t.after(() => rmSync(secretRoot, { recursive: true }));
	const apiPort = await unusedPort();
	const { child, output } = startProduction(apiPort, broker.port, passwordFile);
	t.after(() => stop(child));
	const baseUrl = `http://127.0.0.1:${apiPort}`;
	const ready = await waitForResponse(`${baseUrl}/ready`, child, output);
	assert.equal(ready.status, 200);
	assert.deepEqual(await ready.json(), { status: "ready" });

	for (const [index, name] of [
		"valid-image-png-source.json",
		"valid-image-jpeg-source.json",
	].entries()) {
		const source = JSON.parse(
			readFileSync(
				new URL(
					`../../../packages/protocol/fixtures/print-job-v1/${name}`,
					import.meta.url,
				),
				"utf8",
			),
		) as PrintJob;
		const response = await fetch(`${baseUrl}/api/jobs`, {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify(source),
		});
		const expected: JobResult = {
			schema_version: "1",
			kind: "job_result",
			job_id: source.job_id,
			device_id: deviceId,
			status: "delivered_to_printer",
			bytes_sent: 8,
		};
		assert.equal(response.status, 200);
		assert.deepEqual(await response.json(), expected);
		assert.deepEqual(receivedJobs[index]?.content.blocks, [
			{ type: "raster", width: 8, height: 1, data_base64: "qg==" },
		]);
	}

	const mcp = new Client(
		{ name: "paperbridge-production-bundle", version: "1.0.0" },
		{ versionNegotiation: { mode: { pin: "2026-07-28" } } },
	);
	t.after(() => mcp.close());
	await mcp.connect(
		new StreamableHTTPClientTransport(new URL(`${baseUrl}/mcp`)),
	);
	assert.deepEqual(
		(await mcp.listTools()).tools.map((tool) => tool.name),
		["paperbridge_print"],
	);
	const mcpResult = await mcp.callTool({
		name: "paperbridge_print",
		arguments: {
			content: {
				kind: "receipt",
				blocks: [{ type: "text", text: "Production bundle MCP" }],
			},
		},
	});
	const structured = mcpResult.structuredContent as Record<string, unknown>;
	assert.deepEqual(
		{
			kind: structured.kind,
			device_id: structured.device_id,
			status: structured.status,
		},
		{
			kind: "job_result",
			device_id: deviceId,
			status: "delivered_to_printer",
		},
	);
	assert.doesNotMatch(output(), /test-password/);
	assert.equal(output().includes(passwordFile), false);
});
