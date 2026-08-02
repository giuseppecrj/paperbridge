import { randomUUID } from "node:crypto";
import type { IncomingMessage, ServerResponse } from "node:http";

import {
	createMcpHandler,
	fromJsonSchema,
	McpServer,
} from "@modelcontextprotocol/server";
import {
	localhostHostValidation,
	localhostOriginValidation,
	toNodeHandler,
} from "@modelcontextprotocol/node";
import { printJobSchema, type JobResult } from "@paperbridge/protocol";

import { SubmissionError, type JobSubmissionOptions } from "./job-service.js";

export interface McpEndpoint {
	handle(request: IncomingMessage, response: ServerResponse): Promise<void>;
	close(): Promise<void>;
}

interface McpEndpointOptions {
	deviceId: string;
	submitJob(value: unknown, options?: JobSubmissionOptions): Promise<JobResult>;
	createJobId?: () => string;
	now?: () => string;
}

const inputSchema = fromJsonSchema<{ content: unknown }>({
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
	const validateHost = localhostHostValidation();
	const validateOrigin = localhostOriginValidation();

	return {
		async handle(request, response) {
			if (!validateHost(request, response)) return;
			if (!validateOrigin(request, response)) return;
			await handleMcp(request, response);
		},
		close: () => handler.close(),
	};
}
