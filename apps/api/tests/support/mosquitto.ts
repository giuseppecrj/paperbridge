import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import { createConnection } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

import mqtt from "mqtt";

import { unusedPort } from "./unused-port.js";

const mosquitto = process.env.MOSQUITTO_BIN ?? "mosquitto";
const mosquittoPasswd = process.env.MOSQUITTO_PASSWD_BIN ?? "mosquitto_passwd";

export const mosquittoAvailable = [mosquitto, mosquittoPasswd].every(
	(command) =>
		spawnSync("sh", ["-c", 'command -v "$1" >/dev/null', "sh", command], {
			stdio: "ignore",
		}).status === 0,
);

export interface TestBroker {
	process: ChildProcess;
	port: number;
	username: string;
	password: string;
}

async function waitForPort(port: number): Promise<void> {
	const deadline = Date.now() + 3000;
	while (Date.now() < deadline) {
		try {
			await new Promise<void>((resolve, reject) => {
				const socket = createConnection({ host: "127.0.0.1", port });
				socket.once("connect", () => {
					socket.destroy();
					resolve();
				});
				socket.once("error", reject);
			});
			return;
		} catch {
			await delay(20);
		}
	}
	throw new Error("Mosquitto did not start");
}

export async function startMosquitto(): Promise<TestBroker> {
	const root = await mkdtemp(join(tmpdir(), "paperbridge-mosquitto-"));
	const passwordFile = join(root, "passwd");
	const port = await unusedPort();
	const username = "paperbridge-dev-001";
	const password = "test-password";
	if (
		spawnSync(mosquittoPasswd, ["-b", "-c", passwordFile, username, password])
			.status !== 0
	) {
		throw new Error("Could not create Mosquitto test credentials");
	}
	const configFile = join(root, "mosquitto.conf");
	await writeFile(
		configFile,
		`listener ${port} 127.0.0.1\nallow_anonymous false\npassword_file ${passwordFile}\npersistence false\n`,
	);
	const process = spawn(mosquitto, ["-c", configFile], { stdio: "ignore" });
	await waitForPort(port);
	return { process, port, username, password };
}

export function connectMqtt(
	options: mqtt.IClientOptions,
): Promise<mqtt.MqttClient> {
	const client = mqtt.connect(options);
	return new Promise((resolve, reject) => {
		const onError = (error: Error) => reject(error);
		client.once("error", onError);
		client.once("connect", () => {
			client.removeListener("error", onError);
			resolve(client);
		});
	});
}
