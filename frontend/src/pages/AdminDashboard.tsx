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
import {
  fetchAdminStats,
  deleteSubmission,
  deleteSubmissionsBatch,
  fetchAdminPromoters,
  downloadExport
} from "../utils/api";
import type { AdminStatsResponse } from "../types";

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<AdminStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [showPromotersModal, setShowPromotersModal] = useState(false);
  const [promotersList, setPromotersList] = useState<any[]>([]);
  const [promotersLoading, setPromotersLoading] = useState(false);
  const [promotersError, setPromotersError] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [showBatchConfirmModal, setShowBatchConfirmModal] = useState(false);
  const [exporting, setExporting] = useState(false);

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

  // One-click Excel export of all data
  const handleExport = async () => {
    if (!token) return;
    setExporting(true);
    setError(null);
    try {
      await downloadExport(token);
    } catch (err) {
      if (err instanceof Error && err.message.includes("expired")) {
        sessionStorage.removeItem("admin_token");
        navigate("/admin", { replace: true });
        return;
      }
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  // Select row handler
  const handleSelectRow = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  // Select all handler
  const handleSelectAll = (visibleSubmissions: any[]) => {
    const visibleIds = visibleSubmissions.map((sub) => sub.id);
    const allVisibleSelected = visibleIds.every((id) => selectedIds.includes(id));
    if (allVisibleSelected) {
      setSelectedIds((prev) => prev.filter((id) => !visibleIds.includes(id)));
    } else {
      setSelectedIds((prev) => {
        const newSelected = [...prev];
        visibleIds.forEach((id) => {
          if (!newSelected.includes(id)) {
            newSelected.push(id);
          }
        });
        return newSelected;
      });
    }
  };

  // Batch delete handler
  const handleBatchDeleteClick = () => {
    setShowBatchConfirmModal(true);
  };

  const executeBatchDelete = async () => {
    try {
      if (!token) return;
      setShowBatchConfirmModal(false);
      setLoading(true);
      await deleteSubmissionsBatch(token, selectedIds);
      setSelectedIds([]);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete submissions");
    } finally {
      setLoading(false);
    }
  };

  // Promoters card click handler
  const handlePromotersCardClick = async () => {
    if (!token) return;
    setShowPromotersModal(true);
    setPromotersLoading(true);
    setPromotersError(null);
    try {
      const list = await fetchAdminPromoters(token);
      setPromotersList(list);
    } catch (err) {
      setPromotersError(err instanceof Error ? err.message : "Failed to load promoters");
    } finally {
      setPromotersLoading(false);
    }
  };

  // Delete submission handler
  const handleDeleteClick = (id: number) => {
    if (deleteConfirmId === id) {
      executeDelete(id);
    } else {
      setDeleteConfirmId(id);
      // Auto-reset after 8 seconds (gives the user plenty of time)
      setTimeout(() => {
        setDeleteConfirmId((currentId) => (currentId === id ? null : currentId));
      }, 8000);
    }
  };

  const executeDelete = async (id: number) => {
    try {
      if (!token) return;
      setDeleteConfirmId(null);
      await deleteSubmission(token, id);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete submission");
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
        <div style={{ display: "flex", gap: 10 }}>
          <button
            className="btn btn-primary btn-sm"
            onClick={handleExport}
            disabled={exporting}
          >
            {exporting ? "Preparing…" : "⬇ Download Excel"}
          </button>
          <button className="btn btn-secondary btn-sm" onClick={handleLogout}>
            🚪 Logout
          </button>
        </div>
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
            <div 
              className="glass-card admin-stat-card clickable"
              onClick={handlePromotersCardClick}
            >
              <div className="admin-stat-value" style={{ color: "var(--accent)" }}>
                {data.total_promoters}
              </div>
              <div className="admin-stat-label">Promoters</div>
            </div>
          </div>

          {/* Submissions Table */}
          <div className="glass-card admin-table-wrapper">
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 16,
              padding: "0 4px"
            }}>
              <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 600 }}>
                {statusFilter ? `${statusFilter.toUpperCase().replace("_", " ")} Submissions` : "All Submissions"}
              </h3>
              {selectedIds.length > 0 && (
                <button
                  className="btn btn-danger btn-sm"
                  onClick={handleBatchDeleteClick}
                  style={{ display: "flex", alignItems: "center", gap: 6 }}
                >
                  🗑 Delete Selected ({selectedIds.length})
                </button>
              )}
            </div>
            {data.submissions.length > 0 ? (
              <table className="admin-table">
                <thead>
                  <tr>
                    <th style={{ width: 40, textAlign: "center" }}>
                      <input
                        type="checkbox"
                        checked={data.submissions.every((sub) => selectedIds.includes(sub.id))}
                        onChange={() => handleSelectAll(data.submissions)}
                        style={{ cursor: "pointer", width: 16, height: 16 }}
                      />
                    </th>
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
                      <td style={{ textAlign: "center" }}>
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(sub.id)}
                          onChange={() => handleSelectRow(sub.id)}
                          style={{ cursor: "pointer", width: 16, height: 16 }}
                        />
                      </td>
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
                            className={`btn ${deleteConfirmId === sub.id ? "btn-danger" : "btn-danger btn-sm"}`}
                            type="button"
                            onClick={() => handleDeleteClick(sub.id)}
                            style={{ 
                              padding: "4px 10px", 
                              fontSize: "0.75rem",
                              background: deleteConfirmId === sub.id ? "#dc2626" : undefined,
                              borderColor: deleteConfirmId === sub.id ? "#dc2626" : undefined
                            }}
                          >
                            {deleteConfirmId === sub.id ? "⚠️ Confirm?" : "🗑 Delete"}
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

      {/* Promoters List Modal */}
      {showPromotersModal && (
        <div className="modal-overlay" onClick={() => setShowPromotersModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">👥 Registered Promoters</h2>
              <button className="modal-close" onClick={() => setShowPromotersModal(false)}>×</button>
            </div>
            <div className="modal-body">
              {promotersLoading && (
                <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}>
                  <div className="spinner" />
                </div>
              )}
              {promotersError && (
                <div className="error-alert">⚠️ {promotersError}</div>
              )}
              {!promotersLoading && !promotersError && (
                <div className="modal-table-wrapper">
                  <table className="modal-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>IC Number</th>
                        <th>Gender</th>
                      </tr>
                    </thead>
                    <tbody>
                      {promotersList.map((p) => (
                        <tr key={p.id}>
                          <td>
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                              <img
                                src={p.avatar || "/avatars/avatar_m1.png"}
                                alt={p.name}
                                style={{
                                  width: 32,
                                  height: 32,
                                  borderRadius: "50%",
                                  objectFit: "cover",
                                }}
                              />
                              <span style={{ fontWeight: 600 }}>{p.name}</span>
                            </div>
                          </td>
                          <td><code>{p.ic_number}</code></td>
                          <td>
                            <span style={{ textTransform: "capitalize" }}>
                              {p.gender || "unknown"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Batch Delete Confirmation Modal */}
      {showBatchConfirmModal && (
        <div className="modal-overlay" onClick={() => setShowBatchConfirmModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">⚠️ Confirm Batch Delete</h2>
              <button className="modal-close" onClick={() => setShowBatchConfirmModal(false)}>×</button>
            </div>
            <div className="modal-body" style={{ textAlign: "center", padding: "30px 24px" }}>
              <div style={{ fontSize: "3rem", marginBottom: 16 }}>🗑️</div>
              <p style={{ fontSize: "1.05rem", fontWeight: 600, color: "#1e293b", marginBottom: 8 }}>
                Are you sure you want to delete {selectedIds.length} submissions?
              </p>
              <p style={{ color: "#64748b", fontSize: "0.9rem", marginBottom: 24 }}>
                This will release the unique username constraints in the database and permanently delete the uploaded image files. This action cannot be undone.
              </p>
              <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
                <button
                  className="btn btn-secondary"
                  onClick={() => setShowBatchConfirmModal(false)}
                >
                  Cancel
                </button>
                <button
                  className="btn btn-danger"
                  onClick={executeBatchDelete}
                >
                  Confirm Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
