import { randomUUID } from "node:crypto";
import type { IncomingMessage, ServerResponse } from "node:http";

import {
	createMcpHandler,
	fromJsonSchema,
	McpServer,
} from "@modelcontextprotocol/server";
import { toNodeHandler } from "@modelcontextprotocol/node";
import {
	printJobSchema,
	type JobResult,
	type PrintJobContent,
} from "@paperbridge/protocol";

import {
	accessError,
	API_JOB_MAX_BYTES,
	HttpError,
	readBody,
	type ApiAccessPolicy,
} from "./http-security.js";
import { SubmissionError, type JobSubmissionOptions } from "./job-service.js";

export interface McpEndpoint {
	handle(request: IncomingMessage, response: ServerResponse): Promise<void>;
	close(): Promise<void>;
}

export type McpAccessPolicy = ApiAccessPolicy;

interface McpEndpointOptions {
	deviceId: string;
	submitJob(value: unknown, options?: JobSubmissionOptions): Promise<JobResult>;
	accessPolicy?: McpAccessPolicy;
	maxBodyBytes?: number;
	createJobId?: () => string;
	now?: () => string;
}

const inputSchema = fromJsonSchema<{ content: PrintJobContent }>({
	type: "object",
	additionalProperties: false,
	required: ["content"],
	properties: { content: printJobSchema.properties.content },
	$defs: printJobSchema.$defs,
});

function toolResult(value: unknown, isError = false) {
	return {
		content: [{ type: "text" as const, text: JSON.stringify(value) }],
		structuredContent: value,
		...(isError ? { isError: true } : {}),
	};
}

export function createMcpEndpoint(options: McpEndpointOptions): McpEndpoint {
	const createJobId = options.createJobId ?? randomUUID;
	const now = options.now ?? (() => new Date().toISOString());
	const handler = createMcpHandler(() => {
		const server = new McpServer({ name: "paperbridge", version: "1.0.0" });
		server.registerTool(
			"paperbridge_print",
			{
				title: "Print a Paperbridge receipt",
				description:
					"Submit one semantic print-job.v1 receipt to the configured Paperbridge device and wait for an honest result. Image blocks accept PNG or JPEG sources and are preprocessed by the Host; Paperbridge resizes them within 576×576 raster dots, so pre-resize large images to reduce upload time. Image jobs may take longer than text jobs. Provide raw Base64 image bytes without a data-URL prefix.",
				inputSchema,
			},
			async ({ content }, context) => {
				try {
					const result = await options.submitJob(
						{
							schema_version: "1",
							job_id: createJobId(),
							device_id: options.deviceId,
							created_at: now(),
							content,
						},
						{ signal: context.mcpReq.signal },
					);
					return toolResult(result, result.status !== "delivered_to_printer");
				} catch (error) {
					if (error instanceof SubmissionError) {
						return toolResult(error.response(), true);
					}
					throw error;
				}
			},
		);
		return server;
	});
	const handleMcp = toNodeHandler(handler);
	const maximum = options.maxBodyBytes ?? API_JOB_MAX_BYTES;

	return {
		async handle(request, response) {
			const denied = accessError(request, options.accessPolicy);
			if (denied) {
				response.writeHead(403, { "content-type": "application/json" });
				response.end(JSON.stringify({
					jsonrpc: "2.0",
					error: { code: -32000, message: denied.message },
					id: null,
				}));
				return;
			}
			let body: Buffer;
			try {
				body = await readBody(request, maximum);
			} catch (error) {
				if (!(error instanceof HttpError)) throw error;
				response.writeHead(413, { "content-type": "application/json" });
				response.end(JSON.stringify({
					jsonrpc: "2.0",
					error: { code: -32000, message: "Request body is too large" },
					id: null,
				}));
				return;
			}
			// The SDK's Node adapter accepts this structural request shape. Its
			// JSON parsing and response/cancellation handling see only bounded bytes.
			await handleMcp({
				method: request.method,
				url: request.url,
				headers: request.headers,
				async *[Symbol.asyncIterator]() {
					yield body;
				},
			}, response);
		},
		close: () => handler.close(),
	};
}
