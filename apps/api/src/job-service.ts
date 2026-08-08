import {
	encodePrintJob,
	parsePrintJob,
	ProtocolValidationError,
	type JobResult,
	type PrintJob,
} from "@paperbridge/protocol";

import {
	ImagePreparationError,
	preparePrintJob,
	type ImageDecoder,
} from "./image-preparer.js";
import { sharpImageDecoder } from "./sharp-image-decoder.js";

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
	private readonly inFlight = new Set<Promise<JobResult>>();
	private draining = false;

	constructor(
		private readonly deviceId: string,
		private readonly broker: JobBroker,
		private readonly imageDecoder: ImageDecoder = sharpImageDecoder,
	) {}

	submit(
		value: unknown,
		options: JobSubmissionOptions = {},
	): Promise<JobResult> {
		if (this.draining) {
			return Promise.reject(
				new SubmissionError(503, "SERVICE_DRAINING", "failed"),
			);
		}
		const submission = this.submitAccepted(value, options);
		this.inFlight.add(submission);
		const complete = () => this.inFlight.delete(submission);
		void submission.then(complete, complete);
		return submission;
	}

	async drain(): Promise<void> {
		this.draining = true;
		await Promise.allSettled(this.inFlight);
	}

	isDraining(): boolean {
		return this.draining;
	}

	private async submitAccepted(
		value: unknown,
		options: JobSubmissionOptions,
	): Promise<JobResult> {
		let job: PrintJob;
		try {
			job = await preparePrintJob(parsePrintJob(value), this.imageDecoder);
			job = parsePrintJob(job);
		} catch (error) {
			if (
				error instanceof ProtocolValidationError ||
				error instanceof ImagePreparationError
			) {
				throw new SubmissionError(400, "INVALID_PRINT_JOB");
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
