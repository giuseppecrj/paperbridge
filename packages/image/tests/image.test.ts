import assert from "node:assert/strict";
import test from "node:test";

import { MAX_RASTER_BYTES, prepareRaster } from "../src/index.js";

test("packs a deterministic multi-row Floyd-Steinberg raster", () => {
	const raster = prepareRaster({
		width: 8,
		height: 2,
		pixels: Uint8Array.from([0, 255, 0, 255, 0, 255, 0, 255, 255, 0, 255, 0, 255, 0, 255, 0]),
	});
	assert.deepEqual([...raster.data], [0xaa, 0x55]);
});

test("accepts the maximum proposed raster allocation", () => {
	const raster = prepareRaster({
		width: 128,
		height: 24,
		pixels: new Uint8Array(128 * 24),
	});
	assert.equal(raster.data.length, MAX_RASTER_BYTES);
});
