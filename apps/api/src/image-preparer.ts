import { Buffer } from "node:buffer";

import type {
	PrintJobImageBlock,
	PrintJobRasterBlock,
} from "@paperbridge/protocol";

export const MAX_RASTER_WIDTH = 576;
export const MAX_RASTER_HEIGHT = 576;
export const MAX_RASTER_BYTES = 41_472;

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

export const MAX_IMAGE_SOURCE_BASE64_CHARACTERS = 2 * 1024 * 1024;

const PNG_SIGNATURE = Buffer.from("89504e470d0a1a0a", "hex");
const JPEG_SOI = Buffer.from("ffd8ff", "hex");

type ImageMimeType = PrintJobImageBlock["mime_type"];

export interface ImageDecoder {
	decode(
		bytes: Uint8Array,
		mimeType: ImageMimeType,
		maximum: { width: number; height: number },
	): Promise<DecodedImage>;
}

export class ImagePreparationError extends Error {}

function isObject(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null;
}

function isImageSourceBlock(value: unknown): value is PrintJobImageBlock {
	return isObject(value) && value.type === "image";
}

function sourceBytes(block: PrintJobImageBlock): Uint8Array {
	if (
		(block.mime_type !== "image/png" && block.mime_type !== "image/jpeg") ||
		typeof block.data_base64 !== "string" ||
		block.data_base64.length === 0 ||
		block.data_base64.length > MAX_IMAGE_SOURCE_BASE64_CHARACTERS ||
		block.data_base64.length % 4 !== 0 ||
		!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(
			block.data_base64,
		)
	) {
		throw new ImagePreparationError("invalid image source");
	}
	const bytes = Buffer.from(block.data_base64, "base64");
	const signature = block.mime_type === "image/png" ? PNG_SIGNATURE : JPEG_SOI;
	if (!bytes.subarray(0, signature.length).equals(signature)) {
		throw new ImagePreparationError(
			"image MIME type does not match source bytes",
		);
	}
	return bytes;
}

function rasterBlock(image: DecodedImage): PrintJobRasterBlock {
	const raster = prepareRaster(image);
	return {
		type: "raster",
		width: raster.width,
		height: raster.height,
		data_base64: Buffer.from(raster.data).toString("base64"),
	};
}

export async function preparePrintJob<
	T extends { content: { blocks: unknown[] } },
>(job: T, decoder: ImageDecoder): Promise<T> {
	const blocks = await Promise.all(
		job.content.blocks.map(async (block) => {
			if (!isImageSourceBlock(block)) return block;
			try {
				return rasterBlock(
					await decoder.decode(sourceBytes(block), block.mime_type, {
						width: MAX_RASTER_WIDTH,
						height: MAX_RASTER_HEIGHT,
					}),
				);
			} catch (error) {
				if (error instanceof ImagePreparationError) throw error;
				throw new ImagePreparationError("image decode failed");
			}
		}),
	);
	return { ...job, content: { ...job.content, blocks } } as T;
}
