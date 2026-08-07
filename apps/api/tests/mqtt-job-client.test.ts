import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";

import type { JobResult, PrintJob } from "@paperbridge/protocol";

import {
	connectionOptions,
	MqttJobClient,
	type MqttConnection,
} from "../src/mqtt-job-client.js";
import { SubmissionError } from "../src/job-service.js";

class FakeClient extends EventEmitter implements MqttConnection {
	connected = false;
	subscriptions: Array<[string, { qos: 1 }]> = [];
	published: Array<[string, string, { qos: 1; retain: false }]> = [];
	ended = false;

	subscribe(
		topic: string,
		options: { qos: 1 },
		callback: (error?: Error) => void,
	): void {
		this.subscriptions.push([topic, options]);
		callback();
	}

	publish(
		topic: string,
		payload: string,
		options: { qos: 1; retain: false },
		callback: (error?: Error) => void,
	): void {
		this.published.push([topic, payload, options]);
		callback();
	}

	end(): void {
		this.ended = true;
	}

	open(): void {
		this.connected = true;
		this.emit("connect");
	}

	message(topic: string, result: unknown): void {
		this.emit("message", topic, Buffer.from(JSON.stringify(result)));
	}
}

const job = {
	schema_version: "1",
	job_id: "job-hello-001",
	device_id: "paperbridge-dev-001",
} as PrintJob;
const delivered: JobResult = {
	schema_version: "1",
	kind: "job_result",
	job_id: "job-hello-001",
	device_id: "paperbridge-dev-001",
	status: "delivered_to_printer",
	bytes_sent: 28,
};

function adapter(client: FakeClient, timeoutMs = 1000): MqttJobClient {
	return new MqttJobClient(
		{
			deviceId: "paperbridge-dev-001",
			host: "127.0.0.1",
			port: 1883,
			username: "device",
			password: "password",
			clientId: "api-test",
			timeoutMs,
		},
		client,
	);
}

test("uses certificate verification and SNI only when MQTT TLS is enabled", () => {
	const config = {
		deviceId: "paperbridge-dev-001",
		host: "abc.emqxsl.com",
		port: 8883,
		username: "device",
		password: "password",
		clientId: "api-test",
		timeoutMs: 1000,
		tls: { ca: Buffer.from("CA"), servername: "abc.emqxsl.com" },
	};

	assert.deepEqual(connectionOptions(config), {
		host: "abc.emqxsl.com",
		port: 8883,
		protocol: "mqtts",
		protocolVersion: 4,
		clientId: "api-test",
		username: "device",
		password: "password",
		clean: true,
		reconnectPeriod: 1000,
		ca: Buffer.from("CA"),
		servername: "abc.emqxsl.com",
		rejectUnauthorized: true,
	});
	assert.equal(
		connectionOptions({ ...config, tls: undefined }).protocol,
		"mqtt",
	);
});

test("readiness follows the connected result-subscription lifecycle", () => {
	const client = new FakeClient();
	const broker = adapter(client);
	assert.equal(broker.isReady(), false);

	client.open();
	assert.equal(broker.isReady(), true);

	client.connected = false;
	assert.equal(broker.isReady(), false);
});

test("publishes once with QoS 1 and resolves only the correlated result", async () => {
	const client = new FakeClient();
	const broker = adapter(client);
	client.open();
	assert.deepEqual(client.subscriptions, [
		["v1/devices/paperbridge-dev-001/job-results", { qos: 1 }],
	]);

	const pending = broker.submit(job, JSON.stringify(job));
	assert.deepEqual(client.published, [
		[
			"v1/devices/paperbridge-dev-001/print-jobs",
			JSON.stringify(job),
			{ qos: 1, retain: false },
		],
	]);
	client.message("v1/devices/paperbridge-dev-001/job-results", {
		...delivered,
		job_id: "other-job",
	});
	client.message("v1/devices/paperbridge-dev-001/job-results", delivered);

	assert.deepEqual(await pending, delivered);
});

test("reports broker unavailable without publishing", async () => {
	const client = new FakeClient();
	const broker = adapter(client);

	await assert.rejects(
		broker.submit(job, JSON.stringify(job)),
		(error: unknown) =>
			error instanceof SubmissionError &&
			error.statusCode === 503 &&
			error.errorCode === "BROKER_UNAVAILABLE",
	);
	assert.deepEqual(client.published, []);
});

test("times out as unknown without automatically republishing", async () => {
	const client = new FakeClient();
	const broker = adapter(client, 5);
	client.open();

	await assert.rejects(
		broker.submit(job, JSON.stringify(job)),
		(error: unknown) =>
			error instanceof SubmissionError &&
			error.statusCode === 504 &&
			error.responseStatus === "unknown" &&
			error.errorCode === "DEVICE_RESULT_TIMEOUT",
	);
	assert.equal(client.published.length, 1);
});

test("cancellation releases the waiter and ignores a late result", async () => {
	const client = new FakeClient();
	const broker = adapter(client, 25);
	const controller = new AbortController();
	client.open();

	const cancelled = broker.submit(job, JSON.stringify(job), {
		signal: controller.signal,
	});
	controller.abort();

	await assert.rejects(
		cancelled,
		(error: unknown) =>
			error instanceof DOMException && error.name === "AbortError",
	);
	assert.equal(client.published.length, 1);
	client.message("v1/devices/paperbridge-dev-001/job-results", delivered);

	const retried = broker.submit(job, JSON.stringify(job));
	assert.equal(client.published.length, 2);
	client.message("v1/devices/paperbridge-dev-001/job-results", delivered);
	assert.deepEqual(await retried, delivered);
});

test("closing rejects pending waiters instead of leaving HTTP requests hanging", async () => {
	const client = new FakeClient();
	const broker = adapter(client);
	client.open();
	const pending = broker.submit(job, JSON.stringify(job));

	broker.close();

	await assert.rejects(
		pending,
		(error: unknown) =>
			error instanceof SubmissionError &&
			error.errorCode === "SERVICE_SHUTTING_DOWN",
	);
	assert.equal(client.ended, true);
});

test("rejects a concurrent duplicate job id without a second publish", async () => {
	const client = new FakeClient();
	const broker = adapter(client);
	client.open();
	const first = broker.submit(job, JSON.stringify(job));

	await assert.rejects(
		broker.submit(job, JSON.stringify(job)),
		(error: unknown) =>
			error instanceof SubmissionError &&
			error.statusCode === 409 &&
			error.errorCode === "JOB_ALREADY_PENDING",
	);
	assert.equal(client.published.length, 1);
	client.message("v1/devices/paperbridge-dev-001/job-results", delivered);
	await first;
});
