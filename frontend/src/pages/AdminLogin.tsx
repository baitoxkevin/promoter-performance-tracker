/**
 * Admin Login Page — PIN entry for admin access.
 *
 * Features:
 *  - Centered card with large PIN input
 *  - Auto-submits when 4 digits are entered
 *  - Shake animation on wrong PIN
 *  - Redirects to admin dashboard on success
 *  - Stores token in sessionStorage (expires when browser closes)
 */

import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { adminLogin } from "../utils/api";

export default function AdminLogin() {
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Check if already logged in
  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    if (token) {
      navigate("/admin/dashboard", { replace: true });
    }
  }, [navigate]);

  // Auto-focus the PIN input
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Handle PIN input
  const handlePinChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, "").slice(0, 8); // Digits only, max 8
    setPin(value);
    setError(null);

    // Auto-submit when 4+ digits entered
    if (value.length >= 4) {
      setLoading(true);
      try {
        const response = await adminLogin(value);
        if (response.success && response.token) {
          sessionStorage.setItem("admin_token", response.token);
          navigate("/admin/dashboard", { replace: true });
        } else {
          setError(response.message || "Invalid PIN");
          setPin("");
          inputRef.current?.focus();
        }
      } catch {
        setError("Connection error. Please try again.");
        setPin("");
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <div className="page">
      <div className="pin-container">
        <div className="glass-card pin-card">
          <div className="pin-icon">🔐</div>
          <h1 className="pin-title">Admin Access</h1>
          <p className="pin-subtitle">Enter the admin PIN to continue</p>

          <input
            ref={inputRef}
            className="pin-input"
            type="password"
            inputMode="numeric"
            placeholder="••••"
            value={pin}
            onChange={handlePinChange}
            disabled={loading}
            autoComplete="off"
          />

          {error && <div className="pin-error">{error}</div>}

          {loading && (
            <div style={{ marginTop: 20, display: "flex", justifyContent: "center" }}>
              <div className="spinner" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
