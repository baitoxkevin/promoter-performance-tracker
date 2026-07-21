/**
 * Upload Page — Snap & upload in one tap.
 *
 * Returning promoter (name + IC remembered on this phone):
 *   tap "Snap & Upload" → camera → shutter → uploads instantly → result shows.
 * First time: fill name + IC once; from then on it's one tap per customer.
 * Gallery path stays batch: select several, review, then upload.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import { savePromoterInfo, loadPromoterInfo, clearPromoterInfo } from "../utils/storage";
import { compressImages } from "../utils/compress";
import { uploadScreenshots, fetchBatchStatus } from "../utils/api";
import UploadZone from "../components/UploadZone";
import { EVENTS } from "../constants";
import type { BatchStatusResponse } from "../types";

const STATUS_LABEL: Record<string, string> = {
  valid: "Registered",
  duplicate: "Duplicate",
  ocr_failed: "Failed",
  pending: "Processing",
};

export default function Upload() {
  const [name, setName] = useState("");
  const [icNumber, setIcNumber] = useState("");
  const [gender, setGender] = useState("female");
  const [event, setEvent] = useState("");
  const [customEvent, setCustomEvent] = useState(false);
  const [remembered, setRemembered] = useState(false);

  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [batchId, setBatchId] = useState<string | null>(null);
  const [batchStatus, setBatchStatus] = useState<BatchStatusResponse | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const saved = loadPromoterInfo();
    if (saved) {
      setName(saved.name);
      setIcNumber(saved.ic_number);
      if (saved.gender) setGender(saved.gender);
      if (saved.event) {
        setEvent(saved.event);
        if (!EVENTS.includes(saved.event)) setCustomEvent(true);
      }
      setRemembered(true);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const startPolling = useCallback((id: string) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    const poll = async () => {
      try {
        const status = await fetchBatchStatus(id);
        setBatchStatus(status);
        if (status.pending === 0 && pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    };
    poll();
    pollingRef.current = setInterval(poll, 1500);
  }, []);

  // Core upload — takes files directly so camera capture can fire it
  // immediately without waiting on a state update.
  const doUpload = useCallback(
    async (toUpload: File[], curName: string, curIc: string, curGender: string, curEvent: string) => {
      if (!curEvent.trim()) {
        setError("Pick your event/location first.");
        return;
      }
      if (!curName.trim() || !curIc.trim()) {
        setError("Enter your name and IC once — then snapping uploads instantly.");
        return;
      }
      if (toUpload.length === 0) return;

      setError(null);
      setUploading(true);
      try {
        savePromoterInfo({
          name: curName.trim(),
          ic_number: curIc.trim(),
          gender: curGender,
          event: curEvent.trim(),
        });
        setRemembered(true);
        const compressed = await compressImages(toUpload);
        const response = await uploadScreenshots(
          curName.trim(),
          curIc.trim(),
          curGender,
          compressed,
          curEvent.trim()
        );
        setFiles([]);
        setBatchId(response.batch_id);
        startPolling(response.batch_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
      } finally {
        setUploading(false);
      }
    },
    [startPolling]
  );

  // Camera: capture → upload straight away (holds the photo only if name/IC
  // aren't filled yet, so a first-timer can complete the form and upload).
  const handleCameraCapture = (captured: File[]) => {
    if (!event.trim() || !name.trim() || !icNumber.trim()) {
      setFiles((prev) => [...prev, ...captured]);
      setError(
        !event.trim()
          ? "Pick your event/location first, then snap."
          : "Enter your name and IC once — then snapping uploads instantly."
      );
      return;
    }
    doUpload(captured, name, icNumber, gender, event);
  };

  // Gallery: add to the tray for review, upload with the button.
  const handleGallerySelect = (selected: File[]) => {
    setFiles((prev) => [...prev, ...selected]);
  };

  const handleRemoveFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleClearSaved = () => {
    clearPromoterInfo();
    setName("");
    setIcNumber("");
    setGender("female");
    setRemembered(false);
  };

  const handleReset = () => {
    setBatchId(null);
    setBatchStatus(null);
    setFiles([]);
    setError(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doUpload(files, name, icNumber, gender, event);
  };

  const handleEventChange = (value: string) => {
    if (value === "__other__") {
      setCustomEvent(true);
      setEvent("");
    } else {
      setCustomEvent(false);
      setEvent(value);
    }
  };

  // ── Processing / results view ──
  if (batchId && batchStatus) {
    const { total, completed, pending, results } = batchStatus;
    const allDone = pending === 0;
    const validCount = results.filter((r) => r.status === "valid").length;
    const dupCount = results.filter((r) => r.status === "duplicate").length;
    const failCount = results.filter((r) => r.status === "ocr_failed").length;
    const progressPercent = total > 0 ? Math.round((completed / total) * 100) : 0;

    return (
      <div className="page page-narrow">
        <div className="section-header">
          <h1 className="section-title">{allDone ? "Done" : "Processing"}</h1>
          <p className="section-subtitle">
            {event ? `${event} · ` : ""}
            {allDone
              ? `${total} photo${total !== 1 ? "s" : ""} processed.`
              : `${completed} of ${total}…`}
          </p>
        </div>

        <div className="glass-card">
          {!allDone && (
            <div className="processing-progress">
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
              </div>
              <div className="progress-label">
                {progressPercent}% ({completed}/{total})
              </div>
            </div>
          )}

          {allDone && (
            <div className="processing-summary">
              <div className="summary-stat valid">
                <span className="summary-value">{validCount}</span>
                <span className="summary-label">Registered</span>
              </div>
              <div className="summary-stat duplicate">
                <span className="summary-value">{dupCount}</span>
                <span className="summary-label">Duplicate</span>
              </div>
              <div className="summary-stat failed">
                <span className="summary-value">{failCount}</span>
                <span className="summary-label">Failed</span>
              </div>
            </div>
          )}

          <div className="processing-results">
            {results.map((item, index) => (
              <div className={`processing-item ${item.status}`} key={index}>
                {item.status === "pending" && <div className="spinner-small" />}
                <div className="processing-item-details">
                  <div className="processing-item-filename">
                    {item.full_name || `Photo ${index + 1}`}
                    {item.member_id ? ` · ID ${item.member_id}` : ""}
                  </div>
                  <div className="processing-item-message">
                    {item.status === "pending" ? "Reading photo…" : item.message}
                  </div>
                </div>
                <span className={`status-badge ${item.status}`}>
                  {STATUS_LABEL[item.status] || item.status}
                </span>
              </div>
            ))}
          </div>

          {allDone ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 20 }}>
              <button className="btn btn-primary btn-full" onClick={handleReset}>
                Snap Next
              </button>
              <Link to="/my-uploads" className="btn btn-secondary btn-full">
                View My Uploads
              </Link>
            </div>
          ) : (
            <div className="processing-indicator">
              <div className="spinner-small" />
              <span>Reading your photo…</span>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Upload / capture view ──
  const infoReady = name.trim() !== "" && icNumber.trim() !== "" && event.trim() !== "";

  return (
    <div className="page page-narrow">
      <div className="section-header">
        <h1 className="section-title">Snap & Upload</h1>
        <p className="section-subtitle">
          Point at the customer's membership screen and shoot — we read the name and member ID
          automatically.
        </p>
      </div>

      <div className="glass-card">
        {/* Event picker — always visible so promoters can switch location */}
        <div className="form-group">
          <label className="form-label" htmlFor="event-select">
            Event / Location
          </label>
          <select
            id="event-select"
            className="form-input"
            value={customEvent ? "__other__" : event}
            onChange={(e) => handleEventChange(e.target.value)}
          >
            <option value="">Select event…</option>
            {EVENTS.map((ev) => (
              <option key={ev} value={ev}>
                {ev}
              </option>
            ))}
            <option value="__other__">Other…</option>
          </select>
          {customEvent && (
            <input
              className="form-input"
              style={{ marginTop: 8 }}
              type="text"
              placeholder="Type event / location"
              value={event}
              onChange={(e) => setEvent(e.target.value)}
              maxLength={100}
            />
          )}
        </div>

        {remembered ? (
          <div className="remember-banner">
            <span>
              Welcome back, <strong>{name}</strong>
            </span>
            <button type="button" className="remember-banner-clear" onClick={handleClearSaved}>
              Not you?
            </button>
          </div>
        ) : (
          <form onSubmit={(e) => e.preventDefault()}>
            <div className="form-group">
              <label className="form-label" htmlFor="promoter-name">
                Your Name
              </label>
              <input
                id="promoter-name"
                className="form-input"
                type="text"
                placeholder="Full name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={100}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="ic-number">
                IC Number
              </label>
              <input
                id="ic-number"
                className="form-input"
                type="text"
                placeholder="e.g. 010203-10-1234"
                value={icNumber}
                onChange={(e) => setIcNumber(e.target.value)}
                maxLength={50}
              />
              <p className="form-hint">Entered once. Used only to identify you — never shown publicly.</p>
            </div>

            <div className="form-group">
              <label className="form-label">Gender</label>
              <div className="gender-toggle-group">
                <button
                  type="button"
                  className={`gender-btn ${gender === "male" ? "active" : ""}`}
                  onClick={() => setGender("male")}
                >
                  Male
                </button>
                <button
                  type="button"
                  className={`gender-btn ${gender === "female" ? "active" : ""}`}
                  onClick={() => setGender("female")}
                >
                  Female
                </button>
              </div>
            </div>
          </form>
        )}

        <UploadZone
          files={files}
          onCameraCapture={handleCameraCapture}
          onGallerySelect={handleGallerySelect}
          onRemoveFile={handleRemoveFile}
          maxFiles={20}
          busy={uploading}
        />

        {error && (
          <div className="error-alert" style={{ marginTop: 14 }}>
            {error}
          </div>
        )}

        {/* Manual upload button — only for gallery batches waiting in the tray */}
        {files.length > 0 && (
          <button
            type="button"
            className="btn btn-primary btn-full"
            style={{ marginTop: 14 }}
            onClick={handleSubmit}
            disabled={uploading || !infoReady}
          >
            {uploading ? "Uploading…" : `Upload ${files.length} Photo${files.length !== 1 ? "s" : ""}`}
          </button>
        )}
      </div>
    </div>
  );
}
