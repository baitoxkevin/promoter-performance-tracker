/**
 * Home & Leaderboard Page — The front page of BaitoTrack.
 *
 * Implements the requested PromoteTrack theme:
 *  - Hero Banner with cartoon illustration and Action buttons
 *  - 4 Dynamic Stats Cards (calculated from backend live data)
 *  - Two-column Leaderboard section:
 *    - Left: Top Promoters table with visual progress bars
 *    - Right: Cute bunny mascot illustration card holding a star
 */

import { Link } from "react-router-dom";
import { fetchLeaderboard } from "../utils/api";
import { usePolling } from "../hooks/usePolling";

export default function Leaderboard() {
  const { data, loading, error } = usePolling(fetchLeaderboard, 5000);

  // Smooth scroll to leaderboard table
  const scrollToLeaderboard = () => {
    document.getElementById("leaderboard-section")?.scrollIntoView({
      behavior: "smooth",
    });
  };

  // Extract Top Promoter and Max Count for Progress Bars
  const topPromoterName = data && data.entries.length > 0 ? data.entries[0].promoter_name : "None";
  const topPromoterCount = data && data.entries.length > 0 ? data.entries[0].valid_count : 0;
  const maxValidCount = data && data.entries.length > 0 ? data.entries[0].valid_count : 1;

  return (
    <div className="page">
      {/* 1. Hero Banner */}
      <header className="hero-banner">
        <div className="hero-content">
          <div className="hero-tag">
            <span>💖 Track. Verify. Reward.</span>
          </div>
          <h1 className="hero-title">Smart Promoter Performance Tracker</h1>
          <div className="hero-subtitle">
            <p className="hero-subtitle-primary">Upload proofs, avoid duplicates, and climb the leaderboard!</p>
            <p className="hero-subtitle-primary">Let's make every new user count.</p>
          </div>
          <div className="hero-buttons">
            <Link to="/upload" className="btn btn-primary">
              ☁️ Upload Proof
            </Link>
            <button className="btn btn-secondary" onClick={scrollToLeaderboard}>
              🏆 View Leaderboard
            </button>
          </div>
        </div>
      </header>

      {/* Loading overlay */}
      {loading && !data && (
        <div className="spinner-overlay">
          <div className="spinner" />
          <p className="spinner-text">Loading performance metrics...</p>
        </div>
      )}

      {/* Error display */}
      {error && !data && (
        <div className="empty-state">
          <div className="empty-icon">⚠️</div>
          <div className="empty-title">Connection Failed</div>
          <div className="empty-text">{error}</div>
        </div>
      )}

      {data && (
        <>
          {/* 2. Stats Bar */}
          <section className="stats-bar">
            {/* Total Promoters */}
            <div className="stat-card">
              <div className="stat-icon-wrapper promoters">👤</div>
              <div className="stat-info">
                <span className="stat-label">Total Promoters</span>
                <span className="stat-value">{data.total_promoters}</span>
                <span className="stat-hint">Active users</span>
              </div>
            </div>

            {/* Valid Signups */}
            <div className="stat-card">
              <div className="stat-icon-wrapper valid">🛡️</div>
              <div className="stat-info">
                <span className="stat-label">Valid Signups</span>
                <span className="stat-value">{data.total_valid}</span>
                <span className="stat-hint">Verified & unique</span>
              </div>
            </div>

            {/* Today's Signups */}
            <div className="stat-card">
              <div className="stat-icon-wrapper today">✅</div>
              <div className="stat-info">
                <span className="stat-label">Today's Signups</span>
                <span className="stat-value">{data.today_valid}</span>
                <span className="stat-hint">New this morning</span>
              </div>
            </div>

            {/* Top Promoter */}
            <div className="stat-card">
              <div className="stat-icon-wrapper top">🏆</div>
              <div className="stat-info">
                <span className="stat-label">Top Promoter</span>
                <span className="stat-value" style={{ fontSize: "1.2rem", paddingTop: 4 }}>
                  {topPromoterName}
                </span>
                <span className="stat-hint">{topPromoterCount} signups</span>
              </div>
            </div>
          </section>

          {/* 3. Leaderboard Split Section */}
          <section id="leaderboard-section" className="leaderboard-container">
            {/* Left: Top Promoters Table */}
            <div className="table-card">
              <div className="card-title-wrapper">
                <span className="card-title-icon">👑</span>
                <h2 className="card-title">Top Promoters</h2>
              </div>

              {data.entries.length > 0 ? (
                <div className="table-wrapper">
                  <table className="custom-table">
                    <thead>
                      <tr>
                        <th className="rank-badge-col">Rank</th>
                        <th>Promoter Name</th>
                        <th>Valid Signups</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.entries.map((entry) => {
                        // Determine rank pill styling
                        let rankClass = "normal";
                        if (entry.rank === 1) rankClass = "gold";
                        else if (entry.rank === 2) rankClass = "silver";
                        else if (entry.rank === 3) rankClass = "bronze";

                        const rankEmoji = entry.rank === 1 ? "🥇" : entry.rank === 2 ? "🥈" : entry.rank === 3 ? "🥉" : entry.rank;

                        // Calculate percentage for visual progress bar
                        const progressPercent = Math.max(
                          5,
                          (entry.valid_count / maxValidCount) * 100
                        );

                        return (
                          <tr key={entry.rank}>
                            <td className="rank-badge-col">
                              <span className={`rank-pill ${rankClass}`}>
                                {rankEmoji}
                              </span>
                            </td>
                            <td style={{ fontWeight: 600 }}>{entry.promoter_name}</td>
                            <td>
                              <div className="progress-bar-container">
                                <div className="progress-bar-bg">
                                  <div
                                    className="progress-bar-fill"
                                    style={{ width: `${progressPercent}%` }}
                                  />
                                </div>
                                <span style={{ fontWeight: 600, color: "var(--primary)" }}>
                                  {entry.valid_count}
                                </span>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-icon">📈</div>
                  <div className="empty-title">No rankings yet</div>
                  <div className="empty-text">
                    Rankings will populate dynamically as soon as screenshots are scanned.
                  </div>
                </div>
              )}
            </div>

            {/* Right: Bunny Card */}
            <aside className="leaderboard-bunny-card">
              <img
                src="/baito_bunny.png"
                alt="BaitoTrack Bunny Mascot"
                className="bunny-image"
              />
              <h3 style={{ fontSize: "1.1rem", marginBottom: 8, color: "var(--primary)" }}>
                Keep it up!
              </h3>
              <p className="bunny-text">
                Every validated signup gets you closer to the top spot. Check back for real-time updates!
              </p>
            </aside>
          </section>
        </>
      )}
    </div>
  );
}
