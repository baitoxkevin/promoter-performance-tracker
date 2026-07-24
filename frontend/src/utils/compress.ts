/**
 * Client-side image compression using the Canvas API.
 * Reduces file size before uploading to the server.
 * Supports auto-converting iPhone HEIC/HEIF images to JPEG.
 */

import heic2any from "heic2any";

/** Maximum width/height for compressed images (pixels) */
const MAX_DIMENSION = 640;
/** JPEG quality for compression (0.0 to 1.0) */
const QUALITY = 0.85;
/** Maximum file size after compression (bytes) — 100KB */
const MAX_SIZE_BYTES = 100 * 1024;

/** Check if a file is HEIC/HEIF format (iPhone photos) */
function isHEIC(file: File): boolean {
  return file.type === "image/heic" || file.type === "image/heif" ||
    file.name.toLowerCase().endsWith(".heic") || file.name.toLowerCase().endsWith(".heif");
}

/** Convert HEIC File to JPEG File in the browser using heic2any */
async function convertHeicToJpeg(file: File): Promise<File> {
  try {
    console.log(`[HEIC] Converting ${file.name} to JPEG...`);
    const result = await heic2any({
      blob: file,
      toType: "image/jpeg",
      quality: 0.90,
    });
    
    const blob = Array.isArray(result) ? result[0] : result;
    const newName = file.name.replace(/\.[^.]+$/, ".jpg");
    
    return new File([blob], newName, {
      type: "image/jpeg",
      lastModified: Date.now(),
    });
  } catch (err) {
    console.error("[HEIC] Conversion failed:", err);
    throw new Error("Failed to process HEIC photo. Please convert to JPEG manually or use a standard screenshot.");
  }
}

/**
 * Compress an image file using canvas.
 * HEIC files are converted to JPEG first.
 *
 * Strategy:
 *   1. Auto-convert HEIC to JPEG if needed.
 *   2. Load the image into an HTMLImageElement.
 *   3. Draw it onto a canvas, scaling down if it exceeds MAX_DIMENSION.
 *   4. Export as JPEG with progressive quality reduction if needed.
 *   5. Return the compressed file.
 */
export async function compressImage(file: File): Promise<File> {
  let activeFile = file;

  // Step 1: Handle HEIC to JPEG conversion if needed
  if (isHEIC(file)) {
    try {
      activeFile = await convertHeicToJpeg(file);
    } catch (err) {
      throw err;
    }
  }

  // Step 2: Skip canvas compression if already small enough
  if (activeFile.size <= MAX_SIZE_BYTES) {
    return activeFile;
  }

  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(activeFile);

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
              activeFile.name.replace(/\.[^.]+$/, ".jpg"),
              { type: "image/jpeg", lastModified: Date.now() }
            );
            console.log(`Compressed: ${activeFile.name} (${activeFile.size}→${blob.size} bytes)`);
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
      reject(new Error("Failed to load image. The file may be corrupted or in an unsupported format."));
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
