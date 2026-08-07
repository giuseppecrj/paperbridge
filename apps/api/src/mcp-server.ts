import { randomUUID } from "node:crypto";
import type { IncomingMessage, ServerResponse } from "node:http";

import {
	createMcpHandler,
	fromJsonSchema,
	McpServer,
} from "@modelcontextprotocol/server";
import {
	hostHeaderValidation,
	toNodeHandler,
} from "@modelcontextprotocol/node";
import {
	printJobSchema,
	type JobResult,
	type PrintJobContent,
} from "@paperbridge/protocol";

import { LOOPBACK_HOSTNAMES } from "./env.js";
import { SubmissionError, type JobSubmissionOptions } from "./job-service.js";

export interface McpEndpoint {
	handle(request: IncomingMessage, response: ServerResponse): Promise<void>;
	close(): Promise<void>;
}

export interface McpAccessPolicy {
	allowedHostnames: string[];
	allowedOrigins: string[];
}

interface McpEndpointOptions {
	deviceId: string;
	submitJob(value: unknown, options?: JobSubmissionOptions): Promise<JobResult>;
	accessPolicy?: McpAccessPolicy;
	createJobId?: () => string;
	now?: () => string;
}

const defaultAccessPolicy: McpAccessPolicy = {
	allowedHostnames: LOOPBACK_HOSTNAMES,
	allowedOrigins: ["http://localhost", "http://127.0.0.1", "http://[::1]"],
};

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

function rejectOrigin(response: ServerResponse, message: string): false {
	response.writeHead(403, { "Content-Type": "application/json" });
	response.end(
		JSON.stringify({
			jsonrpc: "2.0",
			error: { code: -32000, message },
			id: null,
		}),
	);
	return false;
}

function originIsAllowed(
	request: IncomingMessage,
	policy: McpAccessPolicy,
): boolean {
	const origin = request.headers.origin;
	if (origin === undefined) return true;
	if (Array.isArray(origin)) return false;
	let parsed: URL;
	try {
		parsed = new URL(origin);
	} catch {
		return false;
	}
	if (LOOPBACK_HOSTNAMES.includes(parsed.hostname)) return true;
	return policy.allowedOrigins.includes(parsed.origin);
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
					"Submit one semantic print-job.v1 receipt to the configured Paperbridge device and wait for an honest result.",
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
	const policy = options.accessPolicy ?? defaultAccessPolicy;
	const validateHost = hostHeaderValidation(policy.allowedHostnames);

	return {
		async handle(request, response) {
			if (!validateHost(request, response)) return;
			if (!originIsAllowed(request, policy)) {
				rejectOrigin(response, "Origin header is not allowed");
				return;
			}
			await handleMcp(request, response);
		},
		close: () => handler.close(),
	};
}
