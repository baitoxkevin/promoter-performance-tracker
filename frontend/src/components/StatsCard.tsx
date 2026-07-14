/**
 * StatsCard — A single statistic display card.
 *
 * Used in the leaderboard stats bar to show aggregate numbers.
 * Supports color variants: default, accent, success.
 */

interface Props {
  value: number;
  label: string;
  variant?: "default" | "accent" | "success";
}

export default function StatsCard({ value, label, variant = "default" }: Props) {
  const valueClass =
    variant === "accent" ? "accent" : variant === "success" ? "success" : "";

  return (
    <div className="glass-card stat-card">
      <div className={`stat-value ${valueClass}`}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
