/**
 * Admin Dashboard Page — Protected view for administrators.
 *
 * Features:
 *  - Stats overview cards (total, valid, duplicate, OCR failed)
 *  - Clickable stat cards to filter submissions by status
 *  - Submissions table with promoter name, username, status badge, timestamp
 *  - Clickable image paths to preview uploaded screenshots
 *  - Auto-refreshes every 10 seconds
 *  - Logout button to clear session
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { fetchAdminStats, deleteSubmission } from "../utils/api";
import type { AdminStatsResponse } from "../types";

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<AdminStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [previewImage, setPreviewImage] = useState<string | null>(null);

  const token = sessionStorage.getItem("admin_token");

  // Redirect to login if no token
  useEffect(() => {
    if (!token) {
      navigate("/admin", { replace: true });
    }
  }, [token, navigate]);

  // Fetch data
  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      const result = await fetchAdminStats(token, statusFilter || undefined);
      setData(result);
      setError(null);
    } catch (err) {
      if (err instanceof Error && err.message.includes("expired")) {
        sessionStorage.removeItem("admin_token");
        navigate("/admin", { replace: true });
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter, navigate]);

  // Initial load and polling
  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Logout
  const handleLogout = () => {
    sessionStorage.removeItem("admin_token");
    navigate("/admin", { replace: true });
  };

  // Delete submission handler
  const handleDelete = async (id: number) => {
    const confirmed = window.confirm(
      "Are you sure you want to delete this submission? This will release the username constraint and delete the image file. This action cannot be undone."
    );
    if (!confirmed) return;

    try {
      if (!token) return;
      await deleteSubmission(token, id);
      loadData(); // Reload stats and submissions list
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete submission");
    }
  };

  // Filter click
  const handleFilterClick = (filter: string) => {
    setStatusFilter((prev) => (prev === filter ? "" : filter));
    setLoading(true);
  };

  // Format timestamp
  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  if (!token) return null;

  return (
    <div className="page page-wide">
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 28,
        }}
      >
        <div>
          <h1 className="section-title" style={{ textAlign: "left", marginBottom: 4 }}>
            ⚙️ Admin Dashboard
          </h1>
          <p className="section-subtitle" style={{ textAlign: "left" }}>
            Monitor all submissions and promoter activity
          </p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={handleLogout}>
          🚪 Logout
        </button>
      </div>

      {/* Loading */}
      {loading && !data && (
        <div className="spinner-overlay">
          <div className="spinner" />
          <p className="spinner-text">Loading dashboard...</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          style={{
            color: "var(--danger)",
            padding: "14px 18px",
            background: "var(--danger-bg)",
            borderRadius: "var(--radius-sm)",
            marginBottom: 20,
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {data && (
        <>
          {/* Stats Cards */}
          <div className="admin-stats-grid">
            <div
              className={`glass-card admin-stat-card ${statusFilter === "" ? "active" : ""}`}
              onClick={() => handleFilterClick("")}
            >
              <div className="admin-stat-value" style={{ color: "var(--text-primary)" }}>
                {data.total_submissions}
              </div>
              <div className="admin-stat-label">All</div>
            </div>
            <div
              className={`glass-card admin-stat-card ${statusFilter === "valid" ? "active" : ""}`}
              onClick={() => handleFilterClick("valid")}
            >
              <div className="admin-stat-value" style={{ color: "var(--success)" }}>
                {data.total_valid}
              </div>
              <div className="admin-stat-label">Valid</div>
            </div>
            <div
              className={`glass-card admin-stat-card ${statusFilter === "duplicate" ? "active" : ""}`}
              onClick={() => handleFilterClick("duplicate")}
            >
              <div className="admin-stat-value" style={{ color: "var(--danger)" }}>
                {data.total_duplicate}
              </div>
              <div className="admin-stat-label">Duplicate</div>
            </div>
            <div
              className={`glass-card admin-stat-card ${statusFilter === "ocr_failed" ? "active" : ""}`}
              onClick={() => handleFilterClick("ocr_failed")}
            >
              <div className="admin-stat-value" style={{ color: "var(--warning)" }}>
                {data.total_ocr_failed}
              </div>
              <div className="admin-stat-label">OCR Failed</div>
            </div>
            <div className="glass-card admin-stat-card">
              <div className="admin-stat-value" style={{ color: "var(--accent)" }}>
                {data.total_promoters}
              </div>
              <div className="admin-stat-label">Promoters</div>
            </div>
          </div>

          {/* Submissions Table */}
          <div className="glass-card admin-table-wrapper">
            {data.submissions.length > 0 ? (
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Promoter</th>
                    <th>Username</th>
                    <th>Status</th>
                    <th>Time</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.submissions.map((sub) => (
                    <tr key={sub.id}>
                      <td className="muted">{sub.id}</td>
                      <td>{sub.promoter_name}</td>
                      <td>
                        {sub.extracted_username ? (
                          <span className="username-cell">{sub.extracted_username}</span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        <span className={`status-badge ${sub.status}`}>
                          {sub.status === "valid" && "✓ "}
                          {sub.status === "duplicate" && "✗ "}
                          {sub.status === "ocr_failed" && "? "}
                          {sub.status.replace("_", " ")}
                        </span>
                      </td>
                      <td className="time-cell">{formatTime(sub.created_at)}</td>
                      <td>
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            type="button"
                            onClick={() => setPreviewImage(`/uploads/${sub.image_path}`)}
                            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                          >
                            👁 View
                          </button>
                          <button
                            className="btn btn-danger btn-sm"
                            type="button"
                            onClick={() => handleDelete(sub.id)}
                            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                          >
                            🗑 Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-state">
                <div className="empty-icon">📋</div>
                <div className="empty-title">No Submissions Found</div>
                <div className="empty-text">
                  {statusFilter
                    ? `No submissions with status "${statusFilter}".`
                    : "No submissions have been made yet."}
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* Image Preview Modal */}
      {previewImage && (
        <div
          className="image-preview-overlay"
          onClick={() => setPreviewImage(null)}
        >
          <img src={previewImage} alt="Submission preview" />
        </div>
      )}
    </div>
  );
}
