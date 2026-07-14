/**
 * Leaderboard Page — The home page of the app.
 *
 * Displays:
 *  - Aggregate stats (promoters, valid registrations, total submissions)
 *  - A live indicator showing real-time updates
 *  - Ranked list of promoters by valid submission count
 *
 * Auto-refreshes every 5 seconds via the usePolling hook.
 */

import { fetchLeaderboard } from "../utils/api";
import { usePolling } from "../hooks/usePolling";
import RankCard from "../components/RankCard";
import StatsCard from "../components/StatsCard";

export default function Leaderboard() {
  const { data, loading, error } = usePolling(fetchLeaderboard, 5000);

  return (
    <div className="page">
      {/* Header */}
      <div className="section-header">
        <h1 className="section-title">🏆 Live Leaderboard</h1>
        <p className="section-subtitle">
          Real-time promoter performance rankings
        </p>
        <div style={{ marginTop: 10 }}>
          <span className="live-indicator">
            <span className="live-dot" />
            Live — Auto-updating
          </span>
        </div>
      </div>

      {/* Loading State */}
      {loading && !data && (
        <div className="spinner-overlay">
          <div className="spinner" />
          <p className="spinner-text">Loading leaderboard...</p>
        </div>
      )}

      {/* Error State */}
      {error && !data && (
        <div className="empty-state">
          <div className="empty-icon">⚠️</div>
          <div className="empty-title">Connection Error</div>
          <div className="empty-text">{error}</div>
        </div>
      )}

      {/* Data Loaded */}
      {data && (
        <>
          {/* Stats Bar */}
          <div className="stats-bar">
            <StatsCard
              value={data.total_promoters}
              label="Promoters"
              variant="default"
            />
            <StatsCard
              value={data.total_valid}
              label="Valid Signups"
              variant="accent"
            />
            <StatsCard
              value={data.total_submissions}
              label="Submissions"
              variant="success"
            />
          </div>

          {/* Rank List */}
          {data.entries.length > 0 ? (
            <div className="rank-list">
              {data.entries.map((entry) => (
                <RankCard key={entry.rank} entry={entry} />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">📊</div>
              <div className="empty-title">No Data Yet</div>
              <div className="empty-text">
                Leaderboard will populate as promoters submit screenshots.
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
