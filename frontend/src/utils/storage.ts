/**
 * LocalStorage helper for persisting promoter info across sessions.
 * This implements the "remember me" feature so promoters don't
 * need to re-enter their name and IC number on every upload.
 */

import type { PromoterInfo } from "../types";

const STORAGE_KEY = "promoter_tracker_info";

/**
 * Save promoter info to LocalStorage.
 */
export function savePromoterInfo(info: PromoterInfo): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(info));
  } catch {
    // Silently fail if LocalStorage is unavailable (e.g., private browsing)
    console.warn("Could not save to LocalStorage.");
  }
}

/**
 * Load promoter info from LocalStorage.
 * Returns null if no saved data exists.
 */
export function loadPromoterInfo(): PromoterInfo | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PromoterInfo;
    // Validate that the required fields exist
    if (parsed.name && parsed.ic_number) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Clear saved promoter info from LocalStorage.
 */
export function clearPromoterInfo(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Silently fail
  }
}
