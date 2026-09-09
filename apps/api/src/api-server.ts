import {
	createServer,
	type Server,
	type ServerResponse,
} from "node:http";

import type { JobResult } from "@paperbridge/protocol";

import { SubmissionError, type JobSubmissionOptions } from "./job-service.js";
import type { McpEndpoint } from "./mcp-server.js";
import {
	accessError,
	API_JOB_MAX_BYTES,
	HttpError,
	readBody,
	type ApiAccessPolicy,
} from "./http-security.js";

export { API_JOB_MAX_BYTES } from "./http-security.js";

export interface ApiServerOptions {
	submitJob(value: unknown, options?: JobSubmissionOptions): Promise<JobResult>;
	mcp?: McpEndpoint;
	isReady?: () => boolean;
	maxBodyBytes?: number;
	accessPolicy?: ApiAccessPolicy;
}

function writeJson(
	response: ServerResponse,
	statusCode: number,
	value: unknown,
): void {
	response.writeHead(statusCode, { "content-type": "application/json" });
	response.end(JSON.stringify(value));
}

function resultStatus(result: JobResult): number {
	if (result.status === "delivered_to_printer") return 200;
	if (result.status === "duplicate") return 409;
	if (result.status === "rejected") return 422;
	return 502;
}

export function createApiServer(options: ApiServerOptions): Server {
	const maximum = options.maxBodyBytes ?? API_JOB_MAX_BYTES;
	return createServer(async (request, response) => {
		try {
			const path = (request.url ?? "/").split("?", 1)[0];
			if (path === "/health") {
				writeJson(response, 200, { status: "ok" });
				return;
			}
			if (path === "/ready") {
				const ready = options.isReady?.() ?? false;
				writeJson(response, ready ? 200 : 503, {
					status: ready ? "ready" : "not_ready",
				});
				return;
			}
			if (path === "/mcp" && options.mcp) {
				await options.mcp.handle(request, response);
				return;
			}
			if (path !== "/api/jobs") {
				writeJson(response, 404, {
					status: "rejected",
					error_code: "NOT_FOUND",
				});
				return;
			}
			const denied = accessError(request, options.accessPolicy);
			if (denied) {
				writeJson(response, 403, {
					status: "rejected",
					error_code: denied.errorCode,
				});
				return;
			}
			if (request.method !== "POST") {
				writeJson(response, 405, {
					status: "rejected",
					error_code: "METHOD_NOT_ALLOWED",
				});
				return;
			}
			if (!request.headers["content-type"]?.startsWith("application/json")) {
				writeJson(response, 415, {
					status: "rejected",
					error_code: "UNSUPPORTED_MEDIA_TYPE",
				});
				return;
			}
			const body = await readBody(request, maximum);
			let value: unknown;
			try {
				value = JSON.parse(body.toString("utf8"));
			} catch {
				throw new HttpError(400, "MALFORMED_JSON");
			}
			const result = await options.submitJob(value);
			writeJson(response, resultStatus(result), result);
		} catch (error) {
			if (error instanceof HttpError) {
				writeJson(response, error.statusCode, {
					status: "rejected",
					error_code: error.errorCode,
				});
				return;
			}
			if (error instanceof SubmissionError) {
				writeJson(response, error.statusCode, error.response());
				return;
			}
			writeJson(response, 500, {
				status: "failed",
				error_code: "INTERNAL_ERROR",
			});
		}
	});
}
