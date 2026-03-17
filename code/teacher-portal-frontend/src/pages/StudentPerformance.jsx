import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { getStudentSessions } from "../api/backend.js";

export default function StudentPerformance() {
  const navigate = useNavigate();
  const [studentId, setStudentId] = useState("");
  const [sessions, setSessions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [loadedStudentId, setLoadedStudentId] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = studentId.trim();
    if (!trimmed) return;
    setLoading(true);
    setError("");
    setSessions(null);
    try {
      const data = await getStudentSessions(trimmed);
      // Backend returns { student_id, sessions: [...] }
      setSessions(Array.isArray(data) ? data : data.sessions || []);
      setLoadedStudentId(trimmed);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to load sessions.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-grid">
      <div className="page-header">
        <div>
          <div className="header-eyebrow">Students</div>
          <h1>Student Performance</h1>
          <p>Enter a student ID to view their session history and performance metrics.</p>
        </div>
      </div>

      <div className="panel page-grid">
        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", gap: "12px", alignItems: "flex-end", flexWrap: "wrap" }}
        >
          <div className="field" style={{ flex: "1 1 260px" }}>
            <label htmlFor="student_id_input">Student ID</label>
            <input
              id="student_id_input"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              placeholder="e.g. student_001"
              required
            />
          </div>
          <button
            className="btn btn-primary"
            type="submit"
            disabled={loading}
            style={{ flexShrink: 0 }}
          >
            {loading ? "Loading…" : "Load Sessions"}
          </button>
        </form>
      </div>

      {error && <div className="status error">⚠ {error}</div>}

      {loading && (
        <div className="spinner-wrap">
          <div className="spinner" aria-label="Loading" />
        </div>
      )}

      {!loading && sessions !== null && (
        <div className="page-grid">
          <div>
            <p className="section-title">Sessions for</p>
            <h2 style={{ fontSize: "1.1rem", marginTop: "4px" }}>{loadedStudentId}</h2>
          </div>

          {sessions.length === 0 ? (
            <p className="muted">No sessions found for this student.</p>
          ) : (
            <div style={{ display: "grid", gap: "16px" }}>
              {sessions.map((session) => (
                <SessionSummaryCard
                  key={session.session_id}
                  session={session}
                  studentId={loadedStudentId}
                  onView={() =>
                    navigate(`/students/${loadedStudentId}/sessions/${session.session_id}`)
                  }
                />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function SessionSummaryCard({ session, onView }) {
  // Session data comes from the full session document (steps + session meta) or the lightweight summary
  const sessionMeta = session.session || session;
  const overallSummary = session.overall_summary || session;
  const cleaningPrep = overallSummary.cleaning_preparation || session;

  const isCompleted = sessionMeta.final_step_reached === "completed";

  const safetyItems = overallSummary.critical_safety_concerns || [];

  const hygieneOk = cleaningPrep.hand_hygiene_compliance;
  const solutionOk = cleaningPrep.solution_verified;
  const dressingOk = cleaningPrep.dressing_verified;

  const historScore = overallSummary.history_composite_score;
  const historyInterpretation = overallSummary.history_interpretation;
  const assessmentScore = overallSummary.assessment_score_percentage;
  const allActionsCompleted = cleaningPrep.all_actions_completed;

  const startedAt = sessionMeta.started_at;
  const formattedDate = startedAt
    ? new Date(startedAt).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";

  return (
    <div className="card">
      {/* Top row */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: "12px",
          marginBottom: "16px",
          flexWrap: "wrap",
        }}
      >
        <div>
          <span className="scenario-meta">{sessionMeta.scenario_id || "—"}</span>
          <h3 style={{ marginTop: "6px" }}>{sessionMeta.scenario_title || "Untitled Scenario"}</h3>
        </div>
        <span className={`badge ${isCompleted ? "badge-success" : ""}`}>
          {isCompleted ? "Completed" : (sessionMeta.final_step_reached || "In Progress")}
        </span>
      </div>

      {/* Metrics row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "12px",
          marginBottom: "16px",
        }}
      >
        {/* History Score */}
        <div
          style={{
            background: "var(--bg-elevated)",
            borderRadius: "var(--radius-md)",
            padding: "14px",
            textAlign: "center",
          }}
        >
          <div
            style={{ fontSize: "1.6rem", fontWeight: "800", color: "var(--accent)", lineHeight: 1 }}
          >
            {historScore != null ? `${historScore}/100` : "—"}
          </div>
          <div className="section-title" style={{ marginTop: "6px" }}>
            History
          </div>
          {historyInterpretation && (
            <div
              className="muted"
              style={{
                fontSize: "0.72rem",
                marginTop: "4px",
                overflow: "hidden",
                textOverflow: "ellipsis",
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
              }}
            >
              {historyInterpretation}
            </div>
          )}
        </div>

        {/* Assessment Score */}
        <div
          style={{
            background: "var(--bg-elevated)",
            borderRadius: "var(--radius-md)",
            padding: "14px",
            textAlign: "center",
          }}
        >
          <div
            style={{ fontSize: "1.6rem", fontWeight: "800", color: "var(--accent)", lineHeight: 1 }}
          >
            {assessmentScore != null ? `${assessmentScore}%` : "—"}
          </div>
          <div className="section-title" style={{ marginTop: "6px" }}>
            Assessment
          </div>
        </div>

        {/* Cleaning */}
        <div
          style={{
            background: "var(--bg-elevated)",
            borderRadius: "var(--radius-md)",
            padding: "14px",
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontSize: "1.6rem",
              fontWeight: "800",
              color: allActionsCompleted ? "var(--success-text)" : "var(--error-text)",
              lineHeight: 1,
            }}
          >
            {allActionsCompleted ? "✓" : "✗"}
          </div>
          <div className="section-title" style={{ marginTop: "6px" }}>
            Cleaning
          </div>
          <div className="muted" style={{ fontSize: "0.72rem", marginTop: "4px" }}>
            {allActionsCompleted ? "All Done" : "Incomplete"}
          </div>
        </div>
      </div>

      {/* Safety concerns */}
      {safetyItems.length > 0 && (
        <div style={{ marginBottom: "14px", display: "flex", flexDirection: "column", gap: "6px" }}>
          {safetyItems.slice(0, 2).map((concern, idx) => (
            <span key={idx} className="badge badge-error" style={{ fontSize: "0.78rem" }}>
              ⚠ {concern}
            </span>
          ))}
        </div>
      )}

      {/* Boolean flags row */}
      <div
        style={{
          display: "flex",
          gap: "18px",
          flexWrap: "wrap",
          marginBottom: "18px",
          padding: "12px",
          background: "var(--bg-elevated)",
          borderRadius: "var(--radius-md)",
        }}
      >
        {[
          { label: "Hand Hygiene", value: hygieneOk },
          { label: "Solution Verified", value: solutionOk },
          { label: "Dressing Verified", value: dressingOk },
        ].map(({ label, value }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: "7px" }}>
            <span
              style={{
                width: "10px",
                height: "10px",
                borderRadius: "50%",
                flexShrink: 0,
                background: value ? "var(--accent)" : "var(--error-text)",
                boxShadow: value ? "0 0 6px var(--accent-glow)" : "none",
              }}
            />
            <span className="muted" style={{ fontSize: "0.8rem" }}>
              {label}
            </span>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div
        className="card-footer"
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px" }}
      >
        <span className="muted" style={{ fontSize: "0.8rem" }}>
          {formattedDate}
        </span>
        <button className="btn btn-ghost btn-sm" onClick={onView}>
          View Details →
        </button>
      </div>
    </div>
  );
}
