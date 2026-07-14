/**
 * Navbar — Fixed top navigation bar.
 *
 * Shows the app brand and navigation links.
 * Highlights the active route.
 */

import { NavLink } from "react-router-dom";

export default function Navbar() {
  return (
    <nav className="navbar">
      <div className="navbar-content">
        {/* Brand */}
        <NavLink to="/" className="navbar-brand" style={{ textDecoration: "none" }}>
          <span className="navbar-brand-icon">🏆</span>
          <span className="navbar-brand-text">PromoTracker</span>
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
            <span className="navbar-link-icon">📊</span>
            <span>Leaderboard</span>
          </NavLink>

          <NavLink
            to="/upload"
            className={({ isActive }) =>
              `navbar-link ${isActive ? "active" : ""}`
            }
          >
            <span className="navbar-link-icon">📸</span>
            <span>Upload</span>
          </NavLink>

          <NavLink
            to="/admin"
            className={({ isActive }) =>
              `navbar-link ${isActive ? "active" : ""}`
            }
          >
            <span className="navbar-link-icon">⚙️</span>
            <span>Admin</span>
          </NavLink>
        </div>
      </div>
    </nav>
  );
}
