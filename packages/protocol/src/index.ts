import { Buffer } from "node:buffer";

import { Ajv2020 } from "ajv/dist/2020.js";

import jobResultSchema from "../schemas/job-result.v1.schema.json" with {
	type: "json",
};
import printJobSchema from "../schemas/print-job.v1.schema.json" with {
	type: "json",
};

export const MQTT_JOB_MAX_BYTES = 1024;

type JsonObject = Record<string, unknown>;

export type PrintJob = JsonObject & {
	schema_version: "1";
	job_id: string;
	device_id: string;
};

export type JobResult = JsonObject & {
	schema_version: "1";
	kind: "job_result";
	job_id: string;
	device_id: string;
	status: "delivered_to_printer" | "rejected" | "failed";
	error_code?: string;
	bytes_sent?: number;
};

export class ProtocolValidationError extends Error {
	constructor(
		public readonly code: "INVALID_PRINT_JOB" | "INVALID_JOB_RESULT",
		message: string,
	) {
		super(message);
	}
}

const ajv = new Ajv2020({ allErrors: true, strict: true, strictRequired: false });
const validatePrintJob = ajv.compile<PrintJob>(printJobSchema);
const validateJobResult = ajv.compile<JobResult>(jobResultSchema);

function validationMessage(prefix: string, errors: typeof validatePrintJob.errors): string {
	return `${prefix}: ${ajv.errorsText(errors)}`;
}

export function parsePrintJob(value: unknown): PrintJob {
	if (!validatePrintJob(value)) {
		throw new ProtocolValidationError(
			"INVALID_PRINT_JOB",
			validationMessage("Invalid print-job.v1", validatePrintJob.errors),
		);
	}
	return value as PrintJob;
}

export function parseJobResult(value: unknown): JobResult {
	if (!validateJobResult(value)) {
		throw new ProtocolValidationError(
			"INVALID_JOB_RESULT",
			validationMessage("Invalid job-result.v1", validateJobResult.errors),
		);
	}
	return value as JobResult;
}

export function encodePrintJob(job: PrintJob): string {
	const payload = JSON.stringify(job);
	if (Buffer.byteLength(payload) > MQTT_JOB_MAX_BYTES) {
		throw new RangeError(`Print job exceeds ${MQTT_JOB_MAX_BYTES} bytes`);
	}
	return payload;
}

export function jobTopics(deviceId: string) {
	if (!/^[A-Za-z0-9._-]{1,64}$/.test(deviceId)) {
		throw new Error("deviceId must be a safe MQTT topic segment");
	}
	return {
		jobs: `v1/devices/${deviceId}/print-jobs`,
		results: `v1/devices/${deviceId}/job-results`,
	};
}
