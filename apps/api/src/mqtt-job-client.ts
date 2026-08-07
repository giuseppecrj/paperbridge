import type { Buffer } from "node:buffer";
import { setTimeout as delay } from "node:timers/promises";

import mqtt from "mqtt";

import {
	jobTopics,
	parseJobResult,
	type JobResult,
	type PrintJob,
} from "@paperbridge/protocol";

import { SubmissionError, type JobSubmissionOptions } from "./job-service.js";

export interface MqttConnection {
	connected: boolean;
	on(
		event: "connect" | "close" | "error",
		listener: (error?: Error) => void,
	): this;
	on(
		event: "message",
		listener: (topic: string, payload: Buffer) => void,
	): this;
	subscribe(
		topic: string,
		options: { qos: 1 },
		callback: (error?: Error) => void,
	): void;
	publish(
		topic: string,
		payload: string,
		options: { qos: 1; retain: false },
		callback: (error?: Error) => void,
	): void;
	end(force?: boolean): void;
}

interface MqttTlsConfig {
	ca: Buffer;
	servername: string;
}

export interface MqttJobClientConfig {
	host: string;
	port: number;
	username: string;
	password: string;
	deviceId: string;
	clientId: string;
	timeoutMs: number;
	tls?: MqttTlsConfig;
}

export function connectionOptions(
	config: MqttJobClientConfig,
): mqtt.IClientOptions {
	return {
		host: config.host,
		port: config.port,
		protocol: config.tls ? "mqtts" : "mqtt",
		protocolVersion: 4,
		clientId: config.clientId,
		username: config.username,
		password: config.password,
		clean: true,
		reconnectPeriod: 1000,
		...(config.tls && {
			ca: config.tls.ca,
			servername: config.tls.servername,
			rejectUnauthorized: true,
		}),
	};
}

interface PendingResult {
	resolve(result: JobResult): void;
	reject(error: Error): void;
	timer: ReturnType<typeof setTimeout>;
	signal?: AbortSignal;
	onAbort?: () => void;
}

export class MqttJobClient {
	private readonly client: MqttConnection;
	private readonly topics;
	private readonly pending = new Map<string, PendingResult>();
	private ready = false;

	constructor(
		private readonly config: MqttJobClientConfig,
		client?: MqttConnection,
	) {
		this.topics = jobTopics(config.deviceId);
		this.client =
			client ??
			(mqtt.connect(connectionOptions(config)) as unknown as MqttConnection);
		this.client.on("connect", () => this.subscribe());
		this.client.on("close", () => {
			this.ready = false;
		});
		this.client.on("error", () => {
			this.ready = false;
		});
		this.client.on("message", (topic, payload) =>
			this.handleResult(topic, payload),
		);
	}

	submit(
		job: PrintJob,
		payload: string,
		options: JobSubmissionOptions = {},
	): Promise<JobResult> {
		if (options.signal?.aborted) {
			return Promise.reject(
				new DOMException("Request cancelled", "AbortError"),
			);
		}
		if (!this.isReady()) {
			return Promise.reject(
				new SubmissionError(
					503,
					"BROKER_UNAVAILABLE",
					"failed",
					job.job_id,
					job.device_id,
				),
			);
		}
		if (this.pending.has(job.job_id)) {
			return Promise.reject(
				new SubmissionError(
					409,
					"JOB_ALREADY_PENDING",
					"rejected",
					job.job_id,
					job.device_id,
				),
			);
		}

		return new Promise((resolve, reject) => {
			const signal = options.signal;
			const timer = setTimeout(() => {
				this.pending.delete(job.job_id);
				if (signal && pending.onAbort) {
					signal.removeEventListener("abort", pending.onAbort);
				}
				reject(
					new SubmissionError(
						504,
						"DEVICE_RESULT_TIMEOUT",
						"unknown",
						job.job_id,
						job.device_id,
					),
				);
			}, this.config.timeoutMs);
			const pending: PendingResult = { resolve, reject, timer, signal };
			if (signal) {
				pending.onAbort = () => {
					if (this.pending.get(job.job_id) !== pending) return;
					clearTimeout(timer);
					this.pending.delete(job.job_id);
					signal.removeEventListener("abort", pending.onAbort as () => void);
					reject(new DOMException("Request cancelled", "AbortError"));
				};
			}
			this.pending.set(job.job_id, pending);
			if (signal && pending.onAbort) {
				signal.addEventListener("abort", pending.onAbort, { once: true });
				if (signal.aborted) pending.onAbort();
			}
			if (this.pending.get(job.job_id) !== pending) return;
			this.client.publish(
				this.topics.jobs,
				payload,
				{ qos: 1, retain: false },
				(error) => {
					if (!error || this.pending.get(job.job_id) !== pending) return;
					clearTimeout(timer);
					this.pending.delete(job.job_id);
					if (signal && pending.onAbort) {
						signal.removeEventListener("abort", pending.onAbort);
					}
					reject(
						new SubmissionError(
							503,
							"BROKER_UNAVAILABLE",
							"failed",
							job.job_id,
							job.device_id,
						),
					);
				},
			);
		});
	}

	async waitUntilReady(timeoutMs: number): Promise<boolean> {
		const deadline = Date.now() + timeoutMs;
		while (!this.isReady() && Date.now() < deadline) await delay(10);
		return this.isReady();
	}

	isReady(): boolean {
		return this.ready && this.client.connected;
	}

	close(): void {
		this.ready = false;
		for (const [jobId, pending] of this.pending) {
			clearTimeout(pending.timer);
			if (pending.signal && pending.onAbort) {
				pending.signal.removeEventListener("abort", pending.onAbort);
			}
			pending.reject(
				new SubmissionError(
					503,
					"SERVICE_SHUTTING_DOWN",
					"failed",
					jobId,
					this.config.deviceId,
				),
			);
		}
		this.pending.clear();
		this.client.end(true);
	}

	private subscribe(): void {
		this.ready = false;
		this.client.subscribe(this.topics.results, { qos: 1 }, (error) => {
			this.ready = !error;
		});
	}

	private handleResult(topic: string, payload: Buffer): void {
		if (topic !== this.topics.results) return;
		let result: JobResult;
		try {
			result = parseJobResult(JSON.parse(payload.toString("utf8")));
		} catch {
			return;
		}
		if (result.device_id !== this.config.deviceId) return;
		const pending = this.pending.get(result.job_id);
		if (!pending) return;
		clearTimeout(pending.timer);
		this.pending.delete(result.job_id);
		if (pending.signal && pending.onAbort) {
			pending.signal.removeEventListener("abort", pending.onAbort);
		}
		pending.resolve(result);
	}
}
