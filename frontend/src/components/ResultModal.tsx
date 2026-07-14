/**
 * ResultModal — Displays OCR processing results after upload.
 *
 * Shows each file's result with:
 *  - Status icon (✅ valid, ❌ duplicate, ⚠️ OCR failed)
 *  - Filename
 *  - Extracted username (if found)
 *  - Result message
 */

import type { UploadResponse } from "../types";

interface Props {
  result: UploadResponse;
  onClose: () => void;
}

/** Map status to emoji and color */
const STATUS_CONFIG = {
  valid: { icon: "✅", color: "var(--success)" },
  duplicate: { icon: "❌", color: "var(--danger)" },
  ocr_failed: { icon: "⚠️", color: "var(--warning)" },
} as const;

export default function ResultModal({ result, onClose }: Props) {
  // Count results by status
  const validCount = result.results.filter((r) => r.status === "valid").length;
  const totalCount = result.results.length;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="glass-card modal-content"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div>
            <h2 className="modal-title">Upload Results</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: 4 }}>
              {validCount}/{totalCount} successful
            </p>
          </div>
          <button className="modal-close" onClick={onClose}>
            ✕
          </button>
        </div>

        {/* Results List */}
        {result.results.map((item, index) => {
          const config = STATUS_CONFIG[item.status] || STATUS_CONFIG.ocr_failed;

          return (
            <div className="result-item" key={index}>
              <div className="result-icon">{config.icon}</div>
              <div className="result-details">
                <div className="result-filename">{item.filename}</div>
                <div className="result-message">
                  {item.extracted_username && (
                    <>
                      Username: <span className="result-username">{item.extracted_username}</span>
                      <br />
                    </>
                  )}
                  <span style={{ color: config.color }}>{item.message}</span>
                </div>
              </div>
            </div>
          );
        })}

        {/* Close Button */}
        <button
          className="btn btn-primary btn-full"
          onClick={onClose}
          style={{ marginTop: 16 }}
        >
          Done
        </button>
      </div>
    </div>
  );
}
