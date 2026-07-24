/**
 * Client-side image compression using the Canvas API.
 * Reduces file size before uploading to the server.
 */

/** Maximum width/height for compressed images (pixels) */
const MAX_DIMENSION = 800;
/** JPEG quality for compression (0.0 to 1.0) */
const QUALITY = 0.85;
/** Maximum file size after compression (bytes) — 100KB */
const MAX_SIZE_BYTES = 100 * 1024;

/** Check if a file is HEIC/HEIF format (iPhone photos) */
function isHEIC(file: File): boolean {
  return file.type === "image/heic" || file.type === "image/heif" ||
    file.name.toLowerCase().endsWith(".heic") || file.name.toLowerCase().endsWith(".heif");
}

/**
 * Compress an image file using canvas.
 * HEIC files are always converted to JPEG (OpenCV can't read HEIC).
 *
 * Strategy:
 *   1. Load the image into an HTMLImageElement.
 *   2. Draw it onto a canvas, scaling down if it exceeds MAX_DIMENSION.
 *   3. Export as JPEG with progressive quality reduction if needed.
 *   4. Return the compressed file.
 */
export async function compressImage(file: File): Promise<File> {
  const heic = isHEIC(file);

  // Skip if already small enough AND not HEIC (HEIC must be converted to JPEG)
  if (file.size <= MAX_SIZE_BYTES && !heic) {
    return file;
  }

  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);

    img.onload = () => {
      URL.revokeObjectURL(url);

      // Calculate scaled dimensions
      let { width, height } = img;
      // Safety: clamp to reasonable max for mobile browsers
      const MAX_PIXELS = 2000;
      if (width > MAX_PIXELS || height > MAX_PIXELS) {
        const ratio = Math.min(MAX_PIXELS / width, MAX_PIXELS / height);
        width = Math.round(width * ratio);
        height = Math.round(height * ratio);
      } else if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
        const ratio = Math.min(MAX_DIMENSION / width, MAX_DIMENSION / height);
        width = Math.round(width * ratio);
        height = Math.round(height * ratio);
      }

      // Draw onto canvas
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        reject(new Error("Canvas context not available"));
        return;
      }

      ctx.drawImage(img, 0, 0, width, height);

      // Export as JPEG blob with progressive quality reduction
      const tryCompress = (quality: number) => {
        canvas.toBlob(
          (blob) => {
            if (!blob) {
              reject(new Error("Image conversion failed. Please try a different photo."));
              return;
            }

            // If still too large and quality can be reduced further, retry
            if (blob.size > MAX_SIZE_BYTES && quality > 0.3) {
              tryCompress(quality - 0.2);
              return;
            }

            const compressedFile = new File(
              [blob],
              heic ? file.name.replace(/\.[^.]+$/, ".jpg") : file.name.replace(/\.[^.]+$/, ".jpg"),
              { type: "image/jpeg", lastModified: Date.now() }
            );
            console.log(`Compressed: ${file.name} (${file.size}→${blob.size} bytes${heic ? ', HEIC→JPEG' : ''})`);
            resolve(compressedFile);
          },
          "image/jpeg",
          quality
        );
      };

      tryCompress(QUALITY);
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      if (heic) {
        reject(new Error(
          "HEIC photos are not supported by your browser. " +
          "Please convert to JPEG first, or use a different browser (Chrome/Safari)."
        ));
      } else {
        reject(new Error("Failed to load image. The file may be corrupted or in an unsupported format."));
      }
    };

    img.src = url;
  });
}

/**
 * Compress multiple images in parallel.
 */
export async function compressImages(files: File[]): Promise<File[]> {
  return Promise.all(files.map(compressImage));
}
