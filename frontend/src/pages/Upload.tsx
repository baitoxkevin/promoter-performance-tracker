/**
 * Upload Page — Async upload with real-time OCR processing status.
 *
 * Flow:
 *  1. Promoter fills form + selects files
 *  2. Submit → files upload instantly, backend returns batch_id
 *  3. Frontend enters "processing" mode, polls batch status every 3 seconds
 *  4. Each file's status updates in real-time (pending → valid/duplicate/ocr_failed)
 *  5. When all files are processed, shows final summary
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { savePromoterInfo, loadPromoterInfo, clearPromoterInfo } from "../utils/storage";
import { compressImages } from "../utils/compress";
import { uploadScreenshots, fetchBatchStatus } from "../utils/api";
import UploadZone from "../components/UploadZone";
import type { BatchStatusResponse } from "../types";

/** Status config for icons and colors */
const STATUS_CONFIG: Record<string, { icon: string; color: string }> = {
  valid: { icon: "✅", color: "var(--success)" },
  duplicate: { icon: "❌", color: "var(--danger)" },
  ocr_failed: { icon: "⚠️", color: "var(--warning)" },
  pending: { icon: "⏳", color: "var(--accent-blue)" },
};

export default function Upload() {
  // Promoter info (persisted in LocalStorage)
  const [name, setName] = useState("");
  const [icNumber, setIcNumber] = useState("");
  const [gender, setGender] = useState("female");
  const [remembered, setRemembered] = useState(false);

  // File state
  const [files, setFiles] = useState<File[]>([]);

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Processing state (async)
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batchStatus, setBatchStatus] = useState<BatchStatusResponse | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load saved promoter info on mount
  useEffect(() => {
    const saved = loadPromoterInfo();
    if (saved) {
      setName(saved.name);
      setIcNumber(saved.ic_number);
      if (saved.gender) {
        setGender(saved.gender);
      }
      setRemembered(true);
    }
  }, []);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  // Start polling when batchId is set
  const startPolling = useCallback((id: string) => {
    // Clear any existing polling
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }

    const poll = async () => {
      try {
        const status = await fetchBatchStatus(id);
        setBatchStatus(status);

        // Stop polling when all files are processed
        if (status.pending === 0) {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    // Initial fetch
    poll();

    // Poll every 3 seconds
    pollingRef.current = setInterval(poll, 3000);
  }, []);

  // Handle file selection
  const handleFilesSelected = (newFiles: File[]) => {
    setFiles((prev) => [...prev, ...newFiles]);
  };

  // Remove a file from the preview
  const handleRemoveFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // Clear saved info
  const handleClearSaved = () => {
    clearPromoterInfo();
    setName("");
    setIcNumber("");
    setGender("female");
    setRemembered(false);
  };

  // Reset to upload another batch
  const handleReset = () => {
    setBatchId(null);
    setBatchStatus(null);
    setFiles([]);
    setError(null);
  };

  // Submit the upload
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim() || !icNumber.trim()) {
      setError("Please fill in all required fields.");
      return;
    }
    if (files.length === 0) {
      setError("Please select at least one screenshot.");
      return;
    }

    setError(null);
    setUploading(true);

    try {
      // Save promoter info for future sessions
      savePromoterInfo({ name: name.trim(), ic_number: icNumber.trim(), gender });
      setRemembered(true);

      // Compress images before upload
      const compressed = await compressImages(files);

      // Upload to backend (returns immediately with batch_id)
      const response = await uploadScreenshots(
        name.trim(),
        icNumber.trim(),
        gender,
        compressed
      );

      // Enter processing mode
      setBatchId(response.batch_id);
      setFiles([]); // Clear file previews

      // Start polling for status
      startPolling(response.batch_id);

    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  // ── Render: Processing Status Panel ──
  if (batchId && batchStatus) {
    const { total, completed, pending, results } = batchStatus;
    const allDone = pending === 0;
    const validCount = results.filter((r) => r.status === "valid").length;
    const dupCount = results.filter((r) => r.status === "duplicate").length;
    const failCount = results.filter((r) => r.status === "ocr_failed").length;
    const progressPercent = total > 0 ? Math.round((completed / total) * 100) : 0;

    return (
      <div className="page">
        <div className="section-header">
          <h1 className="section-title">
            {allDone ? "🎉 Processing Complete!" : "⚙️ Processing Screenshots..."}
          </h1>
          <p className="section-subtitle">
            {allDone
              ? `All ${total} file(s) have been processed.`
              : `${completed} of ${total} file(s) processed...`}
          </p>
        </div>

        <div className="glass-card" style={{ padding: "28px 24px" }}>
          {/* Progress Bar */}
          <div className="processing-progress">
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <div className="progress-label">
              {progressPercent}% ({completed}/{total})
            </div>
          </div>

          {/* Summary Stats (only when done) */}
          {allDone && (
            <div className="processing-summary">
              <div className="summary-stat valid">
                <span className="summary-icon">✅</span>
                <span className="summary-value">{validCount}</span>
                <span className="summary-label">Valid</span>
              </div>
              <div className="summary-stat duplicate">
                <span className="summary-icon">❌</span>
                <span className="summary-value">{dupCount}</span>
                <span className="summary-label">Duplicate</span>
              </div>
              <div className="summary-stat failed">
                <span className="summary-icon">⚠️</span>
                <span className="summary-value">{failCount}</span>
                <span className="summary-label">Failed</span>
              </div>
            </div>
          )}

          {/* Per-file Results */}
          <div className="processing-results">
            {results.map((item, index) => {
              const config = STATUS_CONFIG[item.status] || STATUS_CONFIG.pending;
              return (
                <div
                  className={`processing-item ${item.status}`}
                  key={index}
                >
                  <div className="processing-item-icon">
                    {item.status === "pending" ? (
                      <div className="spinner-small" />
                    ) : (
                      config.icon
                    )}
                  </div>
                  <div className="processing-item-details">
                    <div className="processing-item-filename">
                      File {index + 1}
                    </div>
                    <div
                      className="processing-item-message"
                      style={{ color: config.color }}
                    >
                      {item.status === "pending" ? "Waiting for OCR..." : item.message}
                    </div>
                    {item.extracted_username && (
                      <div className="processing-item-username">
                        👤 {item.extracted_username}
                      </div>
                    )}
                  </div>
                  <div className="processing-item-status" style={{ color: config.color }}>
                    {item.status.toUpperCase()}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Action Button */}
          {allDone && (
            <button
              className="btn btn-primary btn-full"
              onClick={handleReset}
              style={{ marginTop: 20 }}
            >
              📸 Upload More Screenshots
            </button>
          )}

          {/* Pulsing indicator while processing */}
          {!allDone && (
            <div className="processing-indicator">
              <div className="spinner" style={{ width: 24, height: 24, borderWidth: 3 }} />
              <span>OCR engine is processing your screenshots...</span>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Render: Upload Form ──
  return (
    <div className="page">
      {/* Header */}
      <div className="section-header">
        <h1 className="section-title">📸 Upload Screenshots</h1>
        <p className="section-subtitle">
          Upload app registration screenshots for OCR verification
        </p>
      </div>

      {/* Form Card */}
      <div className="glass-card" style={{ padding: "28px 24px" }}>
        <form onSubmit={handleSubmit}>
          {/* Remembered Info Banner */}
          {remembered && (
            <div className="remember-banner">
              <span className="remember-banner-icon">💾</span>
              <span>
                Welcome back, <strong>{name}</strong>! Your info is saved.
              </span>
              <button
                type="button"
                className="remember-banner-clear"
                onClick={handleClearSaved}
              >
                Clear
              </button>
            </div>
          )}

          {/* Promoter Name */}
          <div className="form-group">
            <label className="form-label" htmlFor="promoter-name">
              Promoter Name *
            </label>
            <input
              id="promoter-name"
              className="form-input"
              type="text"
              placeholder="Enter your full name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={100}
            />
          </div>

          {/* IC Number */}
          <div className="form-group">
            <label className="form-label" htmlFor="ic-number">
              IC Number *
            </label>
            <input
              id="ic-number"
              className="form-input"
              type="text"
              placeholder="Enter your IC number"
              value={icNumber}
              onChange={(e) => setIcNumber(e.target.value)}
              required
              maxLength={50}
            />
            <p className="form-hint">
              Your IC number is used to identify you uniquely. It won't be shown publicly.
            </p>
          </div>

          {/* Gender Selector */}
          <div className="form-group">
            <label className="form-label">
              Gender / 性别 *
            </label>
            <div className="gender-toggle-group">
              <button
                type="button"
                className={`gender-btn male ${gender === "male" ? "active" : ""}`}
                onClick={() => setGender("male")}
              >
                Male / 男生
              </button>
              <button
                type="button"
                className={`gender-btn female ${gender === "female" ? "active" : ""}`}
                onClick={() => setGender("female")}
              >
                Female / 女生
              </button>
            </div>
          </div>

          {/* Upload Zone */}
          <div className="form-group">
            <label className="form-label">Screenshots *</label>
            <UploadZone
              files={files}
              onFilesSelected={handleFilesSelected}
              onRemoveFile={handleRemoveFile}
              maxFiles={20}
            />
          </div>

          {/* Error Message */}
          {error && (
            <div
              style={{
                color: "var(--danger)",
                fontSize: "0.88rem",
                marginBottom: 16,
                padding: "10px 14px",
                background: "var(--danger-bg)",
                borderRadius: "var(--radius-sm)",
              }}
            >
              ⚠️ {error}
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            className="btn btn-primary btn-full"
            disabled={uploading || files.length === 0}
          >
            {uploading ? (
              <>
                <div className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
                Uploading...
              </>
            ) : (
              <>
                🚀 Upload & Scan ({files.length} file{files.length !== 1 ? "s" : ""})
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
