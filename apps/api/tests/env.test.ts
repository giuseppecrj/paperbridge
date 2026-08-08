import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { apiAccessPolicy, mqttPassword } from "../src/env.js";

const passwordName = "PAPERBRIDGE_MQTT_PASSWORD";
const passwordFileName = "PAPERBRIDGE_MQTT_PASSWORD_FILE";

function thrownError(run: () => unknown): Error {
	try {
		run();
	} catch (error) {
		assert(error instanceof Error);
		return error;
	}
	assert.fail("Expected an error");
}

function withMqttPasswordEnvironment<T>(
	values: { password?: string; file?: string },
	run: () => T,
): T {
	const previousPassword = process.env[passwordName];
	const previousFile = process.env[passwordFileName];
	delete process.env[passwordName];
	delete process.env[passwordFileName];
	if (values.password !== undefined)
		process.env[passwordName] = values.password;
	if (values.file !== undefined) process.env[passwordFileName] = values.file;
	try {
		return run();
	} finally {
		if (previousPassword === undefined) delete process.env[passwordName];
		else process.env[passwordName] = previousPassword;
		if (previousFile === undefined) delete process.env[passwordFileName];
		else process.env[passwordFileName] = previousFile;
	}
}

test("builds loopback defaults and one bounded HTTPS proxy authority", () => {
	const previousHost = process.env.PAPERBRIDGE_API_ALLOWED_HOST;
	const previousOrigin = process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN;
	process.env.PAPERBRIDGE_API_ALLOWED_HOST = "paperbridge.example.exe.xyz";
	process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN =
		"https://paperbridge.example.exe.xyz";
	try {
		assert.deepEqual(apiAccessPolicy(), {
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
		});
	} finally {
		if (previousHost === undefined)
			delete process.env.PAPERBRIDGE_API_ALLOWED_HOST;
		else process.env.PAPERBRIDGE_API_ALLOWED_HOST = previousHost;
		if (previousOrigin === undefined)
			delete process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN;
		else process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN = previousOrigin;
	}
});

test("uses the direct MQTT password for local development", () => {
	withMqttPasswordEnvironment({ password: "local-password" }, () => {
		assert.equal(mqttPassword(), "local-password");
	});
});

test("uses the exact MQTT password file contents", () => {
	const root = mkdtempSync(join(tmpdir(), "paperbridge-secret-"));
	const path = join(root, "mqtt-password");
	writeFileSync(path, "file password");
	try {
		withMqttPasswordEnvironment({ file: path }, () => {
			assert.equal(mqttPassword(), "file password");
		});
	} finally {
		rmSync(root, { recursive: true });
	}
});

test("rejects ambiguous MQTT password sources without exposing either value", () => {
	withMqttPasswordEnvironment(
		{ password: "direct-secret", file: "secret-file-path" },
		() => {
			const error = thrownError(mqttPassword);
			assert.equal(
				error.message,
				"PAPERBRIDGE_MQTT_PASSWORD and PAPERBRIDGE_MQTT_PASSWORD_FILE are mutually exclusive",
			);
			assert.doesNotMatch(error.message, /direct-secret|secret-file-path/);
		},
	);
});

test("rejects missing, empty, and unreadable MQTT password sources safely", () => {
	const root = mkdtempSync(join(tmpdir(), "paperbridge-secret-"));
	const emptyPath = join(root, "empty");
	const missingPath = join(root, "missing-sensitive-name");
	writeFileSync(emptyPath, "");
	try {
		for (const [values, message] of [
			[
				{},
				"PAPERBRIDGE_MQTT_PASSWORD or PAPERBRIDGE_MQTT_PASSWORD_FILE is required",
			],
			[{ password: "" }, "PAPERBRIDGE_MQTT_PASSWORD must not be empty"],
			[{ file: "" }, "PAPERBRIDGE_MQTT_PASSWORD_FILE must not be empty"],
			[{ file: emptyPath }, "PAPERBRIDGE_MQTT_PASSWORD_FILE must not be empty"],
			[{ file: root }, "PAPERBRIDGE_MQTT_PASSWORD_FILE could not be read"],
			[
				{ file: missingPath },
				"PAPERBRIDGE_MQTT_PASSWORD_FILE could not be read",
			],
		] as const) {
			withMqttPasswordEnvironment(values, () => {
				const error = thrownError(mqttPassword);
				assert.equal(error.message, message);
				assert.doesNotMatch(error.message, /missing-sensitive-name/);
			});
		}
	} finally {
		rmSync(root, { recursive: true });
	}
});

test("rejects a non-HTTPS proxy origin", () => {
	const previousOrigin = process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN;
	process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN =
		"http://paperbridge.example.exe.xyz";
	try {
		assert.throws(() => apiAccessPolicy(), /must be an HTTPS origin/);
	} finally {
		if (previousOrigin === undefined)
			delete process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN;
		else process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN = previousOrigin;
	}
});
