import assert from "node:assert/strict";
import test from "node:test";

import { prepareRaster } from "../src/index.js";

test("packs a deterministic multi-row Floyd-Steinberg raster", () => {
	const raster = prepareRaster({
		width: 8,
		height: 2,
		pixels: Uint8Array.from([
			0, 255, 0, 255, 0, 255, 0, 255, 255, 0, 255, 0, 255, 0, 255, 0,
		]),
	});
	assert.deepEqual([...raster.data], [0xaa, 0x55]);
});

test("accepts one full-width 576 by 576 raster", () => {
	const raster = prepareRaster({
		width: 576,
		height: 576,
		pixels: new Uint8Array(576 * 576),
	});
	assert.equal(raster.data.length, 41_472);
});
