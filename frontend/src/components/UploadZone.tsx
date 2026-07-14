/**
 * UploadZone — Drag & drop file upload area with preview thumbnails.
 *
 * Features:
 *  - Click to select files from device
 *  - Drag & drop support with visual feedback
 *  - Preview thumbnails for selected images
 *  - Remove individual files before upload
 *  - Accepts only image files (JPEG, PNG, WebP)
 */

import { useState, useRef, useCallback } from "react";

interface Props {
  files: File[];
  onFilesSelected: (files: File[]) => void;
  onRemoveFile: (index: number) => void;
}

export default function UploadZone({ files, onFilesSelected, onRemoveFile }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Filter to only accept image files
  const filterImages = useCallback((fileList: FileList | null): File[] => {
    if (!fileList) return [];
    return Array.from(fileList).filter((f) =>
      f.type.startsWith("image/")
    );
  }, []);

  // Handle click to open file picker
  const handleClick = () => {
    inputRef.current?.click();
  };

  // Handle file input change
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = filterImages(e.target.files);
    if (selected.length > 0) {
      onFilesSelected(selected);
    }
    // Reset input so the same file can be re-selected
    if (inputRef.current) inputRef.current.value = "";
  };

  // Drag & drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = filterImages(e.dataTransfer.files);
    if (dropped.length > 0) {
      onFilesSelected(dropped);
    }
  };

  return (
    <div>
      {/* Drop Zone */}
      <div
        className={`upload-zone ${dragOver ? "drag-over" : ""}`}
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="upload-zone-icon">📁</div>
        <div className="upload-zone-text">
          {dragOver
            ? "Drop images here..."
            : "Tap to select or drag & drop screenshots"}
        </div>
        <div className="upload-zone-hint">
          Supports JPEG, PNG, WebP • Max 5MB per file
        </div>

        <input
          ref={inputRef}
          className="upload-zone-input"
          type="file"
          accept="image/*"
          multiple
          onChange={handleChange}
        />
      </div>

      {/* Preview Grid */}
      {files.length > 0 && (
        <div className="preview-grid">
          {files.map((file, index) => (
            <div key={`${file.name}-${index}`} className="preview-item">
              <img
                src={URL.createObjectURL(file)}
                alt={file.name}
                onLoad={(e) => {
                  // Revoke object URL after image loads to free memory
                  URL.revokeObjectURL((e.target as HTMLImageElement).src);
                }}
              />
              <button
                type="button"
                className="preview-remove"
                onClick={(e) => {
                  e.stopPropagation();
                  onRemoveFile(index);
                }}
                title="Remove"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
