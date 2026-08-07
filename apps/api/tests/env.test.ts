import assert from "node:assert/strict";
import test from "node:test";

import { apiAccessPolicy } from "../src/env.js";

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
		if (previousHost === undefined) delete process.env.PAPERBRIDGE_API_ALLOWED_HOST;
		else process.env.PAPERBRIDGE_API_ALLOWED_HOST = previousHost;
		if (previousOrigin === undefined)
			delete process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN;
		else process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN = previousOrigin;
	}
});

test("rejects a non-HTTPS proxy origin", () => {
	const previousOrigin = process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN;
	process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN = "http://paperbridge.example.exe.xyz";
	try {
		assert.throws(() => apiAccessPolicy(), /must be an HTTPS origin/);
	} finally {
		if (previousOrigin === undefined)
			delete process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN;
		else process.env.PAPERBRIDGE_API_ALLOWED_ORIGIN = previousOrigin;
	}
});
