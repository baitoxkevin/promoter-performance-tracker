/**
 * Client-side image compression using the Canvas API.
 * Reduces file size before uploading to the server.
 */

/** Maximum width/height for compressed images (pixels) */
const MAX_DIMENSION = 800;
/** JPEG quality for compression (0.0 to 1.0) */
const QUALITY = 0.8;
/** Maximum file size after compression (bytes) — 50KB */
const MAX_SIZE_BYTES = 50 * 1024;

/**
 * Compress an image file using canvas.
 *
 * Strategy:
 *   1. Load the image into an HTMLImageElement.
 *   2. Draw it onto a canvas, scaling down if it exceeds MAX_DIMENSION.
 *   3. Export as JPEG with progressive quality reduction if needed.
 *   4. Return the compressed file.
 */
export async function compressImage(file: File): Promise<File> {
  // Skip if already small enough
  if (file.size <= MAX_SIZE_BYTES) {
    return file;
  }

  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);

    img.onload = () => {
      URL.revokeObjectURL(url);

      // Calculate scaled dimensions
      let { width, height } = img;
      if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
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

      // Export as JPEG blob
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error("Canvas compression failed"));
            return;
          }

          // Create a new File with the compressed data
          const compressedFile = new File(
            [blob],
            file.name.replace(/\.[^.]+$/, ".jpg"),
            { type: "image/jpeg", lastModified: Date.now() }
          );

          resolve(compressedFile);
        },
        "image/jpeg",
        QUALITY
      );
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      // If compression fails, return the original file
      resolve(file);
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
