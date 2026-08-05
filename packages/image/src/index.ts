export const MAX_RASTER_WIDTH = 128;
export const MAX_RASTER_HEIGHT = 24;
export const MAX_RASTER_BYTES = 384;

export type DecodedImage = {
	width: number;
	height: number;
	pixels: Uint8Array;
};

export type PreparedRaster = {
	width: number;
	height: number;
	data: Uint8Array;
};

export function prepareRaster(image: DecodedImage): PreparedRaster {
	const { width, height, pixels } = image;
	if (
		!Number.isInteger(width) ||
		!Number.isInteger(height) ||
		width < 1 ||
		height < 1 ||
		width > MAX_RASTER_WIDTH ||
		height > MAX_RASTER_HEIGHT ||
		pixels.length !== width * height
	) {
		throw new RangeError("invalid decoded image dimensions");
	}
	const rowBytes = Math.ceil(width / 8);
	if (rowBytes * height > MAX_RASTER_BYTES) {
		throw new RangeError("prepared raster exceeds byte limit");
	}
	const grayscale = Float64Array.from(pixels);
	const data = new Uint8Array(rowBytes * height);
	for (let y = 0; y < height; y += 1) {
		for (let x = 0; x < width; x += 1) {
			const index = y * width + x;
			const value = grayscale[index] ?? 0;
			const printed = value < 128 ? 0 : 255;
			const error = value - printed;
			if (printed === 0)
				data[y * rowBytes + Math.floor(x / 8)] |= 0x80 >> (x % 8);
			if (x + 1 < width) grayscale[index + 1] += (error * 7) / 16;
			if (y + 1 < height) {
				if (x > 0) grayscale[index + width - 1] += (error * 3) / 16;
				grayscale[index + width] += (error * 5) / 16;
				if (x + 1 < width) grayscale[index + width + 1] += error / 16;
			}
		}
	}
	return { width, height, data };
}
