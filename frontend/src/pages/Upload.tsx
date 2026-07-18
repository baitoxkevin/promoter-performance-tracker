/**
 * Upload Page — Mobile-friendly form for promoters.
 *
 * Features:
 *  - Promoter name + IC number inputs with LocalStorage persistence
 *  - Drag & drop image upload zone with preview thumbnails
 *  - Client-side image compression before upload
 *  - Loading state during OCR processing
 *  - Results modal showing per-file OCR outcomes
 */

import { useState, useEffect } from "react";
import { savePromoterInfo, loadPromoterInfo, clearPromoterInfo } from "../utils/storage";
import { compressImages } from "../utils/compress";
import { uploadScreenshots } from "../utils/api";
import UploadZone from "../components/UploadZone";
import ResultModal from "../components/ResultModal";
import type { UploadResponse } from "../types";

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
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

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

      // Upload to backend
      const response = await uploadScreenshots(
        name.trim(),
        icNumber.trim(),
        gender,
        compressed
      );

      setResult(response);
      setFiles([]); // Clear files after successful upload
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

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
                Processing OCR...
              </>
            ) : (
              <>
                🚀 Upload & Scan ({files.length} file{files.length !== 1 ? "s" : ""})
              </>
            )}
          </button>
        </form>
      </div>

      {/* Results Modal */}
      {result && (
        <ResultModal
          result={result}
          onClose={() => setResult(null)}
        />
      )}
    </div>
  );
}
