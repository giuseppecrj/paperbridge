import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";

import { MQTT_JOB_MAX_BYTES, type JobResult } from "@paperbridge/protocol";

import { SubmissionError } from "./job-service.js";

export interface ApiServerOptions {
	submitJob(value: unknown): Promise<JobResult>;
	maxBodyBytes?: number;
}

class HttpError extends Error {
	constructor(
		public readonly statusCode: number,
		public readonly errorCode: string,
	) {
		super(errorCode);
	}
}

function writeJson(response: ServerResponse, statusCode: number, value: unknown): void {
	response.writeHead(statusCode, { "content-type": "application/json" });
	response.end(JSON.stringify(value));
}

async function readBody(request: IncomingMessage, maximum: number): Promise<Buffer> {
	const chunks: Buffer[] = [];
	let length = 0;
	for await (const chunk of request) {
		const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
		length += bytes.length;
		if (length > maximum) throw new HttpError(413, "PAYLOAD_TOO_LARGE");
		chunks.push(bytes);
	}
	return Buffer.concat(chunks);
}

function resultStatus(result: JobResult): number {
	if (result.status === "delivered_to_printer") return 200;
	if (result.status === "rejected") return 422;
	return 502;
}

export function createApiServer(options: ApiServerOptions): Server {
	const maximum = options.maxBodyBytes ?? MQTT_JOB_MAX_BYTES;
	return createServer(async (request, response) => {
		try {
			const path = (request.url ?? "/").split("?", 1)[0];
			if (path !== "/api/jobs") {
				writeJson(response, 404, { status: "rejected", error_code: "NOT_FOUND" });
				return;
			}
			if (request.method !== "POST") {
				writeJson(response, 405, { status: "rejected", error_code: "METHOD_NOT_ALLOWED" });
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
			writeJson(response, 500, { status: "failed", error_code: "INTERNAL_ERROR" });
		}
	});
}
