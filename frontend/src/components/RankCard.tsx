/**
 * RankCard — A single row in the leaderboard.
 *
 * Displays rank badge (trophy for top 3, number for others),
 * promoter name, masked IC number, and valid registration count.
 */

import type { LeaderboardEntry } from "../types";

interface Props {
  entry: LeaderboardEntry;
}

/** Trophy emoji for the top 3 ranks */
const TROPHIES: Record<number, string> = {
  1: "🥇",
  2: "🥈",
  3: "🥉",
};

export default function RankCard({ entry }: Props) {
  const trophy = TROPHIES[entry.rank];
  const rankClass = entry.rank <= 3 ? `rank-${entry.rank}` : "";

  return (
    <div className={`glass-card glass-card-interactive rank-card ${rankClass}`}>
      {/* Rank Badge */}
      {trophy ? (
        <div className="rank-badge">{trophy}</div>
      ) : (
        <div className="rank-badge-number">{entry.rank}</div>
      )}

      {/* Promoter Info */}
      <div className="rank-info">
        <div className="rank-name">{entry.promoter_name}</div>
        <div className="rank-ic">{entry.ic_number_masked}</div>
      </div>

      {/* Valid Count */}
      <div className="rank-count">
        <div className="rank-count-value">{entry.valid_count}</div>
        <div className="rank-count-label">signups</div>
      </div>
    </div>
  );
}
