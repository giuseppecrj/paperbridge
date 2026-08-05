import { Buffer } from "node:buffer";

import {
	MAX_RASTER_HEIGHT,
	MAX_RASTER_WIDTH,
	prepareRaster,
	type DecodedImage,
} from "@paperbridge/image";
import type {
	PrintJobImageBlock,
	PrintJobRasterBlock,
} from "@paperbridge/protocol";

export const MAX_IMAGE_SOURCE_BASE64_BYTES = 512;

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
		block.data_base64.length > MAX_IMAGE_SOURCE_BASE64_BYTES ||
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

export async function preparePrintJob<T extends { content: { blocks: unknown[] } }>(
	job: T,
	decoder: ImageDecoder,
): Promise<T> {
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
