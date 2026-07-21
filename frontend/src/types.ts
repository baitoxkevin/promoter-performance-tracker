/**
 * TypeScript interfaces matching the backend Pydantic schemas.
 * Used throughout the frontend for type safety.
 */

// ── Upload ──
export interface SubmissionResult {
  filename: string;
  status: "valid" | "duplicate" | "ocr_failed" | "pending";
  extracted_username: string | null;
  full_name?: string | null;
  member_id?: string | null;
  message: string;
}

// ── My Uploads (submission history) ──
export interface MySubmissionItem {
  id: number;
  status: "valid" | "duplicate" | "ocr_failed" | "pending";
  full_name: string | null;
  member_id: string | null;
  event: string | null;
  image_url: string | null;
  created_at: string;
}

export interface MySubmissionsResponse {
  promoter_name: string | null;
  total: number;
  valid: number;
  duplicate: number;
  failed: number;
  submissions: MySubmissionItem[];
}

export interface UploadResponse {
  success: boolean;
  results: SubmissionResult[];
  promoter_name: string;
}

export interface BatchUploadResponse {
  success: boolean;
  batch_id: string;
  total_files: number;
  message: string;
  promoter_name: string;
}

export interface BatchStatusResponse {
  batch_id: string;
  total: number;
  completed: number;
  pending: number;
  results: SubmissionResult[];
}

// ── Leaderboard ──
export interface LeaderboardEntry {
  rank: number;
  promoter_name: string;
  ic_number_masked: string;
  valid_count: number;
  avatar?: string;
}

export interface LeaderboardResponse {
  entries: LeaderboardEntry[];
  total_promoters: number;
  total_valid: number;
  total_submissions: number;
  today_valid: number;
  last_updated: string;
}

// ── Admin ──
export interface AdminLoginResponse {
  success: boolean;
  token: string | null;
  message: string;
}

export interface AdminSubmission {
  id: number;
  promoter_name: string;
  ic_number: string;
  extracted_username: string | null;
  full_name?: string | null;
  member_id?: string | null;
  event?: string | null;
  status: "valid" | "duplicate" | "ocr_failed";
  image_path: string;
  created_at: string;
}

export interface AdminStatsResponse {
  total_promoters: number;
  total_submissions: number;
  total_valid: number;
  total_duplicate: number;
  total_ocr_failed: number;
  submissions: AdminSubmission[];
  events: string[];
  days: string[];
}

// ── Promoter Info (stored in LocalStorage) ──
export interface PromoterInfo {
  name: string;
  ic_number: string;
  gender?: string;
  event?: string;
}
