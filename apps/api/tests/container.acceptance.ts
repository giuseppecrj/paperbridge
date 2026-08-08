import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import { once } from "node:events";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import { randomUUID } from "node:crypto";

import {
	Client,
	StreamableHTTPClientTransport,
} from "@modelcontextprotocol/client";
import { jobTopics, type PrintJob } from "@paperbridge/protocol";
import type mqtt from "mqtt";

import {
	connectMqtt,
	mosquittoAvailable,
	startMosquitto,
} from "./support/mosquitto.js";
import { unusedPort } from "./support/unused-port.js";

interface ContainerInspect {
	Args: string[];
	Config: { Cmd: string[]; Env: string[]; User: string };
	HostConfig: {
		CapDrop: string[];
		NetworkMode: string;
		PortBindings: Record<string, Array<{ HostIp: string; HostPort: string }>>;
		ReadonlyRootfs: boolean;
		RestartPolicy: { Name: string };
		SecurityOpt: string[];
	};
	Mounts: Array<{ Destination: string; RW: boolean; Source: string }>;
	Path: string;
	State: { ExitCode: number };
}

const image = process.env.PAPERBRIDGE_TEST_CONTAINER_IMAGE;
const deviceId = "paperbridge-dev-001";

function docker(args: string[]): string {
	return execFileSync("docker", args, { encoding: "utf8" }).trim();
}

function inspectContainer(name: string): ContainerInspect {
	return JSON.parse(docker(["inspect", name]))[0] as ContainerInspect;
}

async function waitForStatus(
	url: string,
	status: number,
	containerName: string,
): Promise<Response> {
	const deadline = Date.now() + 10_000;
	while (Date.now() < deadline) {
		try {
			const response = await fetch(url);
			if (response.status === status) return response;
		} catch {
			// The container can still be starting or stopping.
		}
		await delay(25);
	}
	throw new Error(
		`container did not return ${status} for ${url}\n${docker(["logs", containerName])}`,
	);
}

function publishDelivered(
	client: mqtt.MqttClient,
	topic: string,
	job: PrintJob,
): Promise<void> {
	return new Promise((resolve, reject) => {
		client.publish(
			topic,
			JSON.stringify({
				schema_version: "1",
				kind: "job_result",
				job_id: job.job_id,
				device_id: deviceId,
				status: "delivered_to_printer",
				bytes_sent: 8,
			}),
			{ qos: 1, retain: false },
			(error) => (error ? reject(error) : resolve()),
		);
	});
}

test("runs the exact API image with hardened local container boundaries", {
	timeout: 30_000,
}, async (t) => {
	assert(image, "PAPERBRIDGE_TEST_CONTAINER_IMAGE is required");
	assert.equal(
		mosquittoAvailable,
		true,
		"mosquitto and mosquitto_passwd are required for container acceptance",
	);
	const broker = await startMosquitto();
	t.after(() => broker.process.kill());
	const topics = jobTopics(deviceId);
	const receivedJobs: PrintJob[] = [];
	let deviceError: Error | undefined;
	let heldJobId: string | undefined;
	let heldResolve: ((job: PrintJob) => void) | undefined;
	const device = await connectMqtt({
		host: "127.0.0.1",
		port: broker.port,
		protocol: "mqtt",
		protocolVersion: 4,
		clientId: "paperbridge-container-test-device",
		username: broker.username,
		password: broker.password,
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
		if (job.job_id === heldJobId) {
			heldResolve?.(job);
			return;
		}
		void publishDelivered(device, topics.results, job).catch((error) => {
			deviceError = error;
		});
	});

	const secretRoot = mkdtempSync(
		join(tmpdir(), "paperbridge-container-secret-"),
	);
	const passwordFile = join(secretRoot, "mqtt-password");
	writeFileSync(passwordFile, broker.password, { mode: 0o444 });
	t.after(() => rmSync(secretRoot, { recursive: true }));
	const apiPort = await unusedPort();
	const containerName = `paperbridge-api-test-${randomUUID()}`;
	docker([
		"run",
		"--detach",
		"--name",
		containerName,
		"--read-only",
		"--cap-drop=ALL",
		"--security-opt=no-new-privileges",
		"--add-host=host.docker.internal:host-gateway",
		"--publish",
		`127.0.0.1:${apiPort}:3000`,
		"--mount",
		`type=bind,source=${passwordFile},target=/run/secrets/mqtt-password,readonly`,
		"--env",
		"PAPERBRIDGE_API_HOST=0.0.0.0",
		"--env",
		"PAPERBRIDGE_API_PORT=3000",
		"--env",
		`PAPERBRIDGE_DEVICE_ID=${deviceId}`,
		"--env",
		"PAPERBRIDGE_MQTT_HOST=host.docker.internal",
		"--env",
		`PAPERBRIDGE_MQTT_PORT=${broker.port}`,
		"--env",
		`PAPERBRIDGE_MQTT_USERNAME=${broker.username}`,
		"--env",
		"PAPERBRIDGE_MQTT_PASSWORD_FILE=/run/secrets/mqtt-password",
		"--env",
		"PAPERBRIDGE_JOB_RESULT_TIMEOUT_MS=1500",
		image,
	]);
	t.after(() => {
		try {
			docker(["rm", "--force", containerName]);
		} catch {
			// The test reports the primary failure.
		}
	});

	const baseUrl = `http://127.0.0.1:${apiPort}`;
	assert.equal(
		(await waitForStatus(`${baseUrl}/health`, 200, containerName)).status,
		200,
	);
	assert.equal(
		(await waitForStatus(`${baseUrl}/ready`, 200, containerName)).status,
		200,
	);

	const container = inspectContainer(containerName);
	assert.equal(container.Config.User, "node");
	assert.equal(container.HostConfig.ReadonlyRootfs, true);
	assert.deepEqual(container.HostConfig.CapDrop, ["ALL"]);
	assert(container.HostConfig.SecurityOpt.includes("no-new-privileges"));
	assert.notEqual(container.HostConfig.NetworkMode, "host");
	assert.equal(container.HostConfig.RestartPolicy.Name, "no");
	assert.deepEqual(container.HostConfig.PortBindings["3000/tcp"], [
		{ HostIp: "127.0.0.1", HostPort: String(apiPort) },
	]);
	assert.equal(
		container.Mounts.some(
			(mount) =>
				mount.Destination === "/run/secrets/mqtt-password" && !mount.RW,
		),
		true,
	);
	assert.equal(
		container.Mounts.some(
			(mount) => mount.Destination === "/var/run/docker.sock",
		),
		false,
	);
	const runtimeMetadata = JSON.stringify([
		container.Config.Env,
		container.Path,
		container.Args,
	]);
	assert.equal(runtimeMetadata.includes(broker.password), false);
	assert.equal(
		container.Config.Env.some((value) =>
			value.startsWith("PAPERBRIDGE_MQTT_PASSWORD="),
		),
		false,
	);
	const imageInspect = JSON.parse(docker(["image", "inspect", image]))[0] as {
		Config: { Cmd: string[]; Env: string[]; User: string };
	};
	assert.equal(imageInspect.Config.User, "node");
	assert.deepEqual(imageInspect.Config.Cmd, ["node", "dist/server.js"]);
	assert.equal(
		JSON.stringify(imageInspect.Config.Env).includes(broker.password),
		false,
	);
	assert.equal(
		docker([
			"history",
			"--no-trunc",
			"--format",
			"{{.CreatedBy}}",
			image,
		]).includes(broker.password),
		false,
	);

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

	const imageJob = JSON.parse(
		readFileSync(
			new URL(
				"../../../packages/protocol/fixtures/print-job-v1/valid-image-png-source.json",
				import.meta.url,
			),
			"utf8",
		),
	) as PrintJob;
	const imageResponse = await fetch(`${baseUrl}/api/jobs`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify(imageJob),
	});
	assert.equal(imageResponse.status, 200);
	assert.equal((await imageResponse.json()).status, "delivered_to_printer");
	assert.deepEqual(
		receivedJobs.find((job) => job.job_id === imageJob.job_id)?.content.blocks,
		[{ type: "raster", width: 8, height: 1, data_base64: "qg==" }],
	);

	let mcp: Client | undefined = new Client(
		{ name: "paperbridge-container-test", version: "1.0.0" },
		{ versionNegotiation: { mode: { pin: "2026-07-28" } } },
	);
	t.after(async () => {
		await mcp?.close();
	});
	await mcp.connect(
		new StreamableHTTPClientTransport(new URL(`${baseUrl}/mcp`)),
	);
	const mcpResult = await mcp.callTool({
		name: "paperbridge_print",
		arguments: {
			content: {
				kind: "receipt",
				blocks: [{ type: "text", text: "Container MCP" }],
			},
		},
	});
	assert.equal(
		(mcpResult.structuredContent as Record<string, unknown>).status,
		"delivered_to_printer",
	);
	await mcp.close();
	mcp = undefined;

	heldJobId = "job-container-drain";
	const heldReceived = new Promise<PrintJob>((resolve) => {
		heldResolve = resolve;
	});
	const heldResponse = fetch(`${baseUrl}/api/jobs`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify({
			schema_version: "1",
			job_id: heldJobId,
			device_id: deviceId,
			created_at: "2026-08-08T00:00:00Z",
			content: {
				kind: "receipt",
				blocks: [{ type: "text", text: "Container drain" }],
			},
		}),
	});
	const heldJob = await heldReceived;
	const stopStarted = Date.now();
	const stopping = spawn("docker", ["stop", "--time", "20", containerName], {
		stdio: "ignore",
	});
	const stopExit = once(stopping, "exit");
	assert.equal(
		(await waitForStatus(`${baseUrl}/ready`, 503, containerName)).status,
		503,
	);
	assert.equal((await fetch(`${baseUrl}/health`)).status, 200);
	const rejected = await fetch(`${baseUrl}/api/jobs`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify({ ...heldJob, job_id: "job-container-rejected" }),
	});
	assert.equal(rejected.status, 503);
	assert.deepEqual(await rejected.json(), {
		status: "failed",
		error_code: "SERVICE_DRAINING",
	});
	const publishedBeforeResult = receivedJobs.length;
	await publishDelivered(device, topics.results, heldJob);
	const deliveredDuringDrain = await heldResponse;
	assert.equal(deliveredDuringDrain.status, 200);
	assert.equal(
		(await deliveredDuringDrain.json()).status,
		"delivered_to_printer",
	);
	assert.equal(receivedJobs.length, publishedBeforeResult);
	const [stopCode, stopSignal] = await stopExit;
	assert.equal(stopCode, 0);
	assert.equal(stopSignal, null);
	assert(Date.now() - stopStarted < 20_000);
	assert.equal(inspectContainer(containerName).State.ExitCode, 0);
	assert.equal(
		docker(["logs", containerName]).includes(broker.password),
		false,
	);
	assert.equal(deviceError, undefined);
});
