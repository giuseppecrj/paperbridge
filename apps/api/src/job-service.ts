import {
	encodePrintJob,
	parsePrintJob,
	ProtocolValidationError,
	type JobResult,
	type PrintJob,
} from "@paperbridge/protocol";

export interface JobSubmissionOptions {
	signal?: AbortSignal;
}

export interface JobBroker {
	submit(
		job: PrintJob,
		payload: string,
		options?: JobSubmissionOptions,
	): Promise<JobResult>;
}

export class SubmissionError extends Error {
	constructor(
		public readonly statusCode: number,
		public readonly errorCode: string,
		public readonly responseStatus:
			| "rejected"
			| "failed"
			| "unknown" = "rejected",
		public readonly jobId?: string,
		public readonly deviceId?: string,
	) {
		super(errorCode);
	}

	response() {
		return {
			...(this.jobId ? { job_id: this.jobId } : {}),
			...(this.deviceId ? { device_id: this.deviceId } : {}),
			status: this.responseStatus,
			error_code: this.errorCode,
		};
	}
}

export class JobSubmissionService {
	constructor(
		private readonly deviceId: string,
		private readonly broker: JobBroker,
	) {}

	async submit(
		value: unknown,
		options: JobSubmissionOptions = {},
	): Promise<JobResult> {
		let job: PrintJob;
		try {
			job = parsePrintJob(value);
		} catch (error) {
			if (error instanceof ProtocolValidationError) {
				throw new SubmissionError(400, error.code);
			}
			throw error;
		}
		if (job.device_id !== this.deviceId) {
			throw new SubmissionError(422, "WRONG_DEVICE");
		}
		let payload: string;
		try {
			payload = encodePrintJob(job);
		} catch (error) {
			if (error instanceof RangeError) {
				throw new SubmissionError(413, "PAYLOAD_TOO_LARGE");
			}
			throw error;
		}
		return this.broker.submit(job, payload, options);
	}
}
