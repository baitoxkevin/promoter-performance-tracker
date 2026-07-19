/**
 * API client for communicating with the FastAPI backend.
 * All API calls go through these typed functions.
 */

import type {
  BatchUploadResponse,
  BatchStatusResponse,
  LeaderboardResponse,
  AdminLoginResponse,
  AdminStatsResponse,
} from "../types";

const API_BASE = "/api";

/**
 * Upload screenshots with promoter info for OCR processing.
 */
export async function uploadScreenshots(
  promoterName: string,
  icNumber: string,
  gender: string,
  files: File[]
): Promise<BatchUploadResponse> {
  const formData = new FormData();
  formData.append("promoter_name", promoterName);
  formData.append("ic_number", icNumber);
  formData.append("gender", gender);

  for (const file of files) {
    formData.append("files", file);
  }

  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Upload failed");
  }

  return res.json();
}

/**
 * Poll the processing status of a batch upload.
 */
export async function fetchBatchStatus(
  batchId: string
): Promise<BatchStatusResponse> {
  const res = await fetch(`${API_BASE}/batch/${batchId}/status`);

  if (!res.ok) {
    throw new Error("Failed to fetch batch status");
  }

  return res.json();
}

/**
 * Fetch the real-time leaderboard data.
 */
export async function fetchLeaderboard(): Promise<LeaderboardResponse> {
  const res = await fetch(`${API_BASE}/leaderboard`);
  if (!res.ok) throw new Error("Failed to fetch leaderboard");
  return res.json();
}

/**
 * Authenticate admin with PIN code.
 */
export async function adminLogin(pin: string): Promise<AdminLoginResponse> {
  const res = await fetch(`${API_BASE}/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin }),
  });

  if (!res.ok) throw new Error("Login request failed");
  return res.json();
}

/**
 * Fetch admin dashboard stats and submissions.
 * Requires a valid admin token in the Authorization header.
 */
export async function fetchAdminStats(
  token: string,
  statusFilter?: string,
  promoterFilter?: string
): Promise<AdminStatsResponse> {
  const params = new URLSearchParams();
  if (statusFilter) params.append("status_filter", statusFilter);
  if (promoterFilter) params.append("promoter_filter", promoterFilter);

  const url = `${API_BASE}/admin/stats${params.toString() ? "?" + params.toString() : ""}`;

  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 401) {
    // Token expired or invalid — clear it
    sessionStorage.removeItem("admin_token");
    throw new Error("Session expired. Please log in again.");
  }

  if (!res.ok) throw new Error("Failed to fetch admin data");
  return res.json();
}

/**
 * Delete a submission by ID.
 * Requires a valid admin token in the Authorization header.
 */
export async function deleteSubmission(
  token: string,
  submissionId: number
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/admin/submission/${submissionId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 401) {
    sessionStorage.removeItem("admin_token");
    throw new Error("Session expired. Please log in again.");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Delete failed" }));
    throw new Error(err.detail || "Delete failed");
  }

  return res.json();
}

/**
 * Delete multiple submissions by their IDs.
 * Requires a valid admin token in the Authorization header.
 */
export async function deleteSubmissionsBatch(
  token: string,
  ids: number[]
): Promise<{ success: boolean; message: string; errors?: string[] }> {
  const res = await fetch(`${API_BASE}/admin/submissions/batch-delete`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ids }),
  });

  if (res.status === 401) {
    sessionStorage.removeItem("admin_token");
    throw new Error("Session expired. Please log in again.");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Batch delete failed" }));
    throw new Error(err.detail || "Batch delete failed");
  }

  return res.json();
}

/**
 * Fetch all registered promoters for admin verification.
 * Requires a valid admin token in the Authorization header.
 */
export async function fetchAdminPromoters(
  token: string
): Promise<Array<{
  id: number;
  name: string;
  ic_number: string;
  gender: string;
  avatar?: string;
  created_at: string;
}>> {
  const res = await fetch(`${API_BASE}/admin/promoters`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 401) {
    sessionStorage.removeItem("admin_token");
    throw new Error("Session expired. Please log in again.");
  }

  if (!res.ok) throw new Error("Failed to fetch promoters list");
  return res.json();
}

