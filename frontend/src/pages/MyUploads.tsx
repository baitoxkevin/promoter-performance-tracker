/**
 * My Uploads — A promoter's own submission history.
 *
 * Uses the IC number saved on this phone (from the Upload page) to look up
 * past submissions: photo thumbnail, extracted name + member ID, status, time.
 * Tap a thumbnail to view the full photo.
 */

import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { loadPromoterInfo } from "../utils/storage";
import { fetchMySubmissions } from "../utils/api";
import type { MySubmissionsResponse } from "../types";

const STATUS_LABEL: Record<string, string> = {
  valid: "Registered",
  duplicate: "Duplicate",
  ocr_failed: "Failed",
  pending: "Processing",
};

function formatTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return d.toLocaleString("en-MY", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function MyUploads() {
  const [icNumber, setIcNumber] = useState<string | null>(null);
  const [manualIc, setManualIc] = useState("");
  const [data, setData] = useState<MySubmissionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const load = useCallback(async (ic: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchMySubmissions(ic);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load uploads");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const saved = loadPromoterInfo();
    if (saved?.ic_number) {
      setIcNumber(saved.ic_number);
      load(saved.ic_number);
    }
  }, [load]);

  const handleManualLookup = (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualIc.trim()) return;
    setIcNumber(manualIc.trim());
    load(manualIc.trim());
  };

  // No saved identity — ask for IC
  if (!icNumber) {
    return (
      <div className="page page-narrow">
        <div className="section-header">
          <h1 className="section-title">My Uploads</h1>
          <p className="section-subtitle">Enter your IC number to view your upload history.</p>
        </div>
        <div className="glass-card">
          <form onSubmit={handleManualLookup}>
            <div className="form-group">
              <label className="form-label" htmlFor="lookup-ic">
                IC Number
              </label>
              <input
                id="lookup-ic"
                className="form-input"
                type="text"
                placeholder="e.g. 010203-10-1234"
                value={manualIc}
                onChange={(e) => setManualIc(e.target.value)}
                required
              />
            </div>
            <button type="submit" className="btn btn-primary btn-full">
              View My Uploads
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="page page-narrow">
      <div className="section-header">
        <h1 className="section-title">My Uploads</h1>
        <p className="section-subtitle">
          {data?.promoter_name ? `${data.promoter_name} · ${data.total} upload${data.total !== 1 ? "s" : ""}` : "Your upload history"}
        </p>
      </div>

      {loading && (
        <div className="spinner-overlay">
          <div className="spinner" />
          <p className="spinner-text">Loading your uploads…</p>
        </div>
      )}

      {error && <div className="error-alert">{error}</div>}

      {data && !loading && (
        <>
          <div className="history-stats">
            <div className="history-stat">
              <div className="history-stat-value valid">{data.valid}</div>
              <div className="history-stat-label">Registered</div>
            </div>
            <div className="history-stat">
              <div className="history-stat-value duplicate">{data.duplicate}</div>
              <div className="history-stat-label">Duplicate</div>
            </div>
            <div className="history-stat">
              <div className="history-stat-value">{data.failed}</div>
              <div className="history-stat-label">Failed</div>
            </div>
          </div>

          {data.submissions.length === 0 ? (
            <div className="glass-card empty-state">
              <div className="empty-title">No uploads yet</div>
              <div className="empty-text">Your uploaded photos will appear here.</div>
              <Link to="/upload" className="btn btn-primary" style={{ marginTop: 16 }}>
                Upload Your First Photo
              </Link>
            </div>
          ) : (
            <div className="history-list">
              {data.submissions.map((item) => (
                <div className="history-item" key={item.id}>
                  {item.image_url ? (
                    <img
                      className="history-thumb"
                      src={item.image_url}
                      alt=""
                      loading="lazy"
                      onClick={() => setPreviewUrl(item.image_url)}
                    />
                  ) : (
                    <div className="history-thumb-placeholder" />
                  )}
                  <div className="history-info">
                    <div className="history-name">{item.full_name || "Name not detected"}</div>
                    <div className="history-meta">
                      {item.member_id ? `ID ${item.member_id} · ` : ""}
                      {formatTime(item.created_at)}
                    </div>
                    {item.event && <div className="history-meta">{item.event}</div>}
                  </div>
                  <span className={`status-badge ${item.status}`}>
                    {STATUS_LABEL[item.status] || item.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {previewUrl && (
        <div className="image-preview-overlay" onClick={() => setPreviewUrl(null)}>
          <img src={previewUrl} alt="Upload preview" />
        </div>
      )}
    </div>
  );
}
