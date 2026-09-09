import type { IncomingMessage } from "node:http";

import { validateHostHeader } from "@modelcontextprotocol/server";

import { LOOPBACK_HOSTNAMES, LOOPBACK_ORIGINS } from "./env.js";

// Includes room for the REST job or MCP envelope around source image data.
export const API_JOB_MAX_BYTES = 2 * 1024 * 1024 + 4096;

export interface ApiAccessPolicy {
	allowedHostnames: string[];
	allowedOrigins: string[];
}

const defaultAccessPolicy: ApiAccessPolicy = {
	allowedHostnames: LOOPBACK_HOSTNAMES,
	allowedOrigins: LOOPBACK_ORIGINS,
};

export function accessError(
	request: IncomingMessage,
	policy: ApiAccessPolicy = defaultAccessPolicy,
): { errorCode: string; message: string } | undefined {
	const host = validateHostHeader(request.headers.host, policy.allowedHostnames);
	if (!host.ok) return { errorCode: "HOST_NOT_ALLOWED", message: host.message };
	if (!originIsAllowed(request.headers.origin, policy)) {
		return {
			errorCode: "ORIGIN_NOT_ALLOWED",
			message: "Origin header is not allowed",
		};
	}
	return undefined;
}

function originIsAllowed(
	origin: string | undefined,
	policy: ApiAccessPolicy,
): boolean {
	if (origin === undefined) return true;
	let parsed: URL;
	try {
		parsed = new URL(origin);
	} catch {
		return false;
	}
	if (origin !== parsed.origin) return false;
	if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return false;
	if (LOOPBACK_HOSTNAMES.includes(parsed.hostname)) return true;
	return policy.allowedOrigins.includes(parsed.origin);
}

export class HttpError extends Error {
	constructor(
		public readonly statusCode: number,
		public readonly errorCode: string,
	) {
		super(errorCode);
	}
}

export async function readBody(
	request: IncomingMessage,
	maximum: number,
): Promise<Buffer> {
	const chunks: Buffer[] = [];
	let length = 0;
	// Keep the socket alive long enough to send 413 when a chunk crosses the bound.
	try {
		for await (const chunk of request.iterator({ destroyOnReturn: false })) {
			const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
			length += bytes.length;
			if (length > maximum) throw new HttpError(413, "PAYLOAD_TOO_LARGE");
			chunks.push(bytes);
		}
	} catch (error) {
		// Discard the remaining upload without buffering after sending 413.
		if (error instanceof HttpError) request.resume();
		throw error;
	}
	return Buffer.concat(chunks, length);
}
