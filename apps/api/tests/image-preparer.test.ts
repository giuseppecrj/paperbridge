import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
	ImagePreparationError,
	preparePrintJob,
	type ImageDecoder,
} from "../src/image-preparer.js";
import { sharpImageDecoder } from "../src/sharp-image-decoder.js";

const job = {
	schema_version: "1",
	job_id: "job-image-001",
	device_id: "paperbridge-dev-001",
	created_at: "2026-08-03T00:00:00Z",
	content: {
		kind: "receipt",
		blocks: [
			{
				type: "image",
				mime_type: "image/png",
				data_base64: "iVBORw0KGgo=",
			},
		],
	},
};

const decoder: ImageDecoder = {
	decode: async () => ({
		width: 8,
		height: 1,
		pixels: Uint8Array.from([0, 255, 0, 255, 0, 255, 0, 255]),
	}),
};

test("prepares a source image as a bounded monochrome raster", async () => {
	const prepared = await preparePrintJob(job, decoder);
	assert.deepEqual(prepared.content.blocks, [
		{
			type: "raster",
			width: 8,
			height: 1,
			data_base64: "qg==",
		},
	]);
	assert.deepEqual(job.content.blocks[0]?.type, "image");
});

test("decodes bounded PNG and JPEG sources with the Node adapter", async () => {
	for (const name of [
		"valid-image-png-source.json",
		"valid-image-jpeg-source.json",
	]) {
		const source = JSON.parse(
			readFileSync(
				new URL(
					`../../../packages/protocol/fixtures/print-job-v1/${name}`,
					import.meta.url,
				),
				"utf8",
			),
		);
		const prepared = await preparePrintJob(source, sharpImageDecoder);
		assert.deepEqual(prepared.content.blocks, [
			{ type: "raster", width: 8, height: 1, data_base64: "qg==" },
		]);
	}
});

test("normalizes decoder failures as invalid image sources", async () => {
	await assert.rejects(
		preparePrintJob(job, {
			decode: async () => Promise.reject(new Error("bad image")),
		}),
		ImagePreparationError,
	);
});

test("rejects a source image whose bytes do not match its MIME type", async () => {
	await assert.rejects(
		preparePrintJob(
			{
				...job,
				content: {
					...job.content,
					blocks: [
						{
							type: "image",
							mime_type: "image/jpeg",
							data_base64: "iVBORw0KGgo=",
						},
					],
				},
			},
			decoder,
		),
		ImagePreparationError,
	);
});
