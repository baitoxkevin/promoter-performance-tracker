/**
 * App — Root component with route configuration.
 * Provides the animated background and navbar on all pages.
 */

import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Leaderboard from "./pages/Leaderboard";
import Upload from "./pages/Upload";
import AdminLogin from "./pages/AdminLogin";
import AdminDashboard from "./pages/AdminDashboard";

export default function App() {
  return (
    <>
      {/* Animated gradient background */}
      <div className="app-background" />

      <div className="app-container">
        <Navbar />

        <Routes>
          <Route path="/" element={<Leaderboard />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/admin" element={<AdminLogin />} />
          <Route path="/admin/dashboard" element={<AdminDashboard />} />
          {/* Wildcard fallback to Leaderboard for unmatched paths (e.g. index.html) */}
          <Route path="*" element={<Leaderboard />} />
        </Routes>
      </div>
    </>
  );
}
