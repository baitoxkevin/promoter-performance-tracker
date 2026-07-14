/**
 * Navbar — Fixed top navigation bar.
 *
 * Designed to match BaitoTrack friendly brand:
 *  - Left side: ⭐ BaitoTrack branding
 *  - Middle: Navigation links (Home, Upload)
 *  - Right side: Admin Login button
 */

import { NavLink } from "react-router-dom";

export default function Navbar() {
  return (
    <nav className="navbar">
      <div className="navbar-content">
        {/* Brand Logo */}
        <NavLink to="/" className="navbar-brand" style={{ textDecoration: "none" }}>
          <span className="navbar-brand-icon">⭐</span>
          <span className="navbar-brand-text">BaitoTrack</span>
        </NavLink>

        {/* Navigation Links */}
        <div className="navbar-links">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `navbar-link ${isActive ? "active" : ""}`
            }
          >
            <span>Home</span>
          </NavLink>

          <NavLink
            to="/upload"
            className={({ isActive }) =>
              `navbar-link ${isActive ? "active" : ""}`
            }
          >
            <span>Upload</span>
          </NavLink>

          {/* Admin Login button on the far right */}
          <NavLink
            to="/admin"
            className="navbar-admin-btn"
            style={{ marginLeft: 16 }}
          >
            🔒 <span>Admin Login</span>
          </NavLink>
        </div>
      </div>
    </nav>
  );
}
