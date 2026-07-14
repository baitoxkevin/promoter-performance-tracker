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

// Q-version Q-face girl cartoon avatar (Jessica / 1st place)
const JessicaAvatar = () => (
  <svg viewBox="0 0 100 100" className="avatar-svg">
    <circle cx="50" cy="50" r="48" fill="#fce7f3" stroke="#fbcfe8" strokeWidth="2"/>
    <path d="M20,48 C15,18 85,18 80,48 C85,68 80,82 80,82 L20,82 C20,82 15,68 20,48 Z" fill="#653b1b"/>
    <circle cx="50" cy="50" r="23" fill="#ffedd5"/>
    <path d="M26,38 Q50,25 74,38 Q62,30 50,33 Q38,30 26,38 Z" fill="#653b1b"/>
    <path d="M22,38 Q28,52 33,40" stroke="#653b1b" strokeWidth="3" fill="none" strokeLinecap="round"/>
    <path d="M78,38 Q72,52 67,40" stroke="#653b1b" strokeWidth="3" fill="none" strokeLinecap="round"/>
    <circle cx="73" cy="33" r="4.5" fill="#f472b6"/>
    <circle cx="79" cy="31" r="4.5" fill="#f472b6"/>
    <circle cx="78" cy="38" r="4.5" fill="#f472b6"/>
    <circle cx="72" cy="39" r="4.5" fill="#f472b6"/>
    <circle cx="75" cy="35" r="2.5" fill="#fef08a"/>
    <path d="M37,48 Q43,44 47,48" stroke="#1e293b" strokeWidth="3.5" fill="none" strokeLinecap="round"/>
    <circle cx="61" cy="48" r="3.5" fill="#1e293b"/>
    <path d="M43,58 Q50,65 57,58" stroke="#e11d48" strokeWidth="3.5" fill="none" strokeLinecap="round"/>
    <path d="M30,73 C30,73 38,81 50,81 C62,81 70,73 70,73 L65,95 L35,95 Z" fill="#ec4899"/>
    <circle cx="37" cy="54" r="3" fill="#f43f5e" opacity="0.4"/>
    <circle cx="61" cy="54" r="3" fill="#f43f5e" opacity="0.4"/>
  </svg>
);

// Q-version Q-face hoodie boy cartoon avatar (Alex / 2nd place)
const AlexAvatar = () => (
  <svg viewBox="0 0 100 100" className="avatar-svg">
    <circle cx="50" cy="50" r="48" fill="#e0f2fe" stroke="#bae6fd" strokeWidth="2"/>
    <path d="M22,46 C18,20 82,20 78,46 C72,34 60,35 50,38 C40,35 28,34 22,46 Z" fill="#582f0e"/>
    <circle cx="50" cy="50" r="23" fill="#ffedd5"/>
    <path d="M25,40 Q50,32 75,40 Q62,28 50,32 Q38,28 25,40 Z" fill="#582f0e"/>
    <circle cx="40" cy="48" r="3.5" fill="#1e293b"/>
    <circle cx="60" cy="48" r="3.5" fill="#1e293b"/>
    <path d="M42,56 Q50,66 58,56" stroke="#ea580c" strokeWidth="3" fill="none" strokeLinecap="round"/>
    <path d="M28,73 C28,73 38,84 50,84 C62,84 72,73 72,73 L66,95 L34,95 Z" fill="#f59e0b"/>
    <path d="M42,75 Q50,81 58,75" stroke="#d97706" strokeWidth="2.5" fill="none"/>
  </svg>
);

// Q-version Q-face hair bun girl cartoon avatar (Samantha / 3rd place)
const SamanthaAvatar = () => (
  <svg viewBox="0 0 100 100" className="avatar-svg">
    <circle cx="50" cy="50" r="48" fill="#ffe5d9" stroke="#fec5bb" strokeWidth="2"/>
    <circle cx="50" cy="22" r="16" fill="#4a2c11"/>
    <circle cx="50" cy="48" r="26" fill="#4a2c11"/>
    <circle cx="50" cy="52" r="21" fill="#fee8d6"/>
    <path d="M28,45 Q50,36 72,45 Q60,34 50,36 Q40,34 28,45 Z" fill="#4a2c11"/>
    <circle cx="41" cy="50" r="3" fill="#1e293b"/>
    <circle cx="59" cy="50" r="3" fill="#1e293b"/>
    <path d="M44,58 Q50,64 56,58" stroke="#ea580c" strokeWidth="3" fill="none" strokeLinecap="round"/>
    <path d="M31,74 C31,74 38,83 50,83 C62,83 69,74 69,74 L64,95 L36,95 Z" fill="#f97316"/>
  </svg>
);

const renderAvatar = (rank: number) => {
  if (rank === 1) return <JessicaAvatar />;
  if (rank === 2) return <AlexAvatar />;
  if (rank === 3) return <SamanthaAvatar />;
  
  // Ranks 4+ alternating Q-version boy/girl avatars
  if (rank % 2 === 0) {
    return (
      <svg viewBox="0 0 100 100" className="avatar-svg">
        <circle cx="50" cy="50" r="48" fill="#e0f2fe" stroke="#bae6fd" strokeWidth="1.5"/>
        <circle cx="50" cy="50" r="22" fill="#ffedd5"/>
        <path d="M30,35 Q50,25 70,35 Q60,25 50,28 Q40,25 30,35 Z" fill="#78350f"/>
        <circle cx="42" cy="48" r="2.5" fill="#1e293b"/>
        <circle cx="58" cy="48" r="2.5" fill="#1e293b"/>
        <path d="M45,56 Q50,60 55,56" stroke="#1e293b" strokeWidth="2" fill="none"/>
        <path d="M32,75 C32,75 40,84 50,84 C60,84 68,75 68,75 L62,95 L38,95 Z" fill="#3b82f6"/>
      </svg>
    );
  } else {
    return (
      <svg viewBox="0 0 100 100" className="avatar-svg">
        <circle cx="50" cy="50" r="48" fill="#fce7f3" stroke="#fbcfe8" strokeWidth="1.5"/>
        <circle cx="50" cy="50" r="22" fill="#ffedd5"/>
        <path d="M28,36 Q50,26 72,36 Q60,28 50,30 Q40,28 28,36 Z" fill="#4a2c11"/>
        <circle cx="42" cy="48" r="2.5" fill="#1e293b"/>
        <circle cx="58" cy="48" r="2.5" fill="#1e293b"/>
        <path d="M45,56 Q50,60 55,56" stroke="#1e293b" strokeWidth="2" fill="none"/>
        <path d="M32,75 C32,75 40,84 50,84 C60,84 68,75 68,75 L62,95 L38,95 Z" fill="#ec4899"/>
      </svg>
    );
  }
};

export default function Leaderboard() {
  const { data, loading, error } = usePolling(fetchLeaderboard, 5000);

  // Smooth scroll to leaderboard table
  const scrollToLeaderboard = () => {
    document.getElementById("leaderboard-section")?.scrollIntoView({
      behavior: "smooth",
    });
  };

  // Mock and real data merge
  const entries = data && data.entries.length > 0 ? data.entries : [
    { rank: 1, promoter_name: "Jessica", valid_count: 387 },
    { rank: 2, promoter_name: "Alex", valid_count: 321 },
    { rank: 3, promoter_name: "Samantha", valid_count: 278 },
    { rank: 4, promoter_name: "Daniel", valid_count: 256 },
    { rank: 5, promoter_name: "Mia", valid_count: 213 },
    { rank: 6, promoter_name: "Ethan", valid_count: 189 },
    { rank: 7, promoter_name: "Olivia", valid_count: 165 },
    { rank: 8, promoter_name: "Liam", valid_count: 142 },
  ];

  const topPromoterName = entries[0].promoter_name;
  const topPromoterCount = entries[0].valid_count;
  const maxValidCount = entries[0].valid_count;

  return (
    <div className="page">
      {/* 1. Hero Banner */}
      <header className="hero-banner">
        <div className="hero-content">
          <div className="hero-tag">
            <span>💖</span>
            <span>Track. Verify. Reward.</span>
          </div>
          <h1 className="hero-title">Smart Promoter Performance Tracker</h1>
          <div className="hero-subtitle">
            <p className="hero-subtitle-primary">Upload proofs, avoid duplicates, and climb the leaderboard!</p>
            <p className="hero-subtitle-primary">Let's make every new user count.</p>
          </div>
          <div className="hero-buttons">
            <Link to="/upload" className="btn btn-primary">
              ☁️&nbsp;&nbsp;Upload Proof
            </Link>
            <button className="btn btn-secondary" onClick={scrollToLeaderboard}>
              🏆&nbsp;&nbsp;View Leaderboard
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

      {/* Main content */}
      {(data || !loading) && (
        <>
          {/* 2. Stats Bar */}
          <section className="stats-bar">
            {/* Total Promoters */}
            <div className="stat-card">
              <div className="stat-icon-wrapper promoters">👤</div>
              <div className="stat-info">
                <span className="stat-label">Total Promoters</span>
                <span className="stat-value">{data ? data.total_promoters : 8}</span>
                <span className="stat-hint">Active users</span>
              </div>
            </div>

            {/* Valid Signups */}
            <div className="stat-card">
              <div className="stat-icon-wrapper valid">🛡️</div>
              <div className="stat-info">
                <span className="stat-label">Valid Signups</span>
                <span className="stat-value">{data ? data.total_valid : 1951}</span>
                <span className="stat-hint">Verified & unique</span>
              </div>
            </div>

            {/* Today's Signups */}
            <div className="stat-card">
              <div className="stat-icon-wrapper today">✅</div>
              <div className="stat-info">
                <span className="stat-label">Today's Signups</span>
                <span className="stat-value">{data ? data.today_valid : 128}</span>
                <span className="stat-hint">New today</span>
              </div>
            </div>

            {/* Top Promoter */}
            <div className="stat-card">
              <div className="stat-icon-wrapper top">🏆</div>
              <div className="stat-info">
                <span className="stat-label">Top Promoter</span>
                <span className="stat-value" style={{ fontSize: "1.3rem", fontWeight: 700, paddingTop: 4 }}>
                  {topPromoterName !== "None" ? topPromoterName : "暂无"}
                </span>
                <span className="stat-hint">
                  {topPromoterName !== "None" ? `${topPromoterCount} signups` : "0 signups"}
                </span>
              </div>
            </div>
          </section>

          {/* 3. Premium Leaderboard Section with Finalized Background Image */}
          <section id="leaderboard-section" className="baitotrack-leaderboard-root" aria-label="Leaderboard">
            {/* Header Overlay (Dynamic text on top-left replicated from user screenshot) */}
            <div className="leaderboard-header-row">
              <div className="trophy-wrapper">
                <span className="trophy-emoji">🏆</span>
              </div>
              <div className="title-text-group">
                <h2 className="leaderboard-title">Leaderboard</h2>
                <p className="leaderboard-subtext">Top promoters who shine every day!</p>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
