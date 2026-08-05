import type { DecodedImage } from "@paperbridge/image";
import sharp from "sharp";

import type { ImageDecoder } from "./image-preparer.js";

export const sharpImageDecoder: ImageDecoder = {
	async decode(bytes, _mimeType, maximum): Promise<DecodedImage> {
		const { data, info } = await sharp(bytes, { limitInputPixels: 4_000_000 })
			.autoOrient()
			.resize({
				width: maximum.width,
				height: maximum.height,
				fit: "inside",
				withoutEnlargement: true,
			})
			.flatten({ background: "#ffffff" })
			.greyscale()
			.raw()
			.toBuffer({ resolveWithObject: true });
		return { width: info.width, height: info.height, pixels: data };
	},
};
