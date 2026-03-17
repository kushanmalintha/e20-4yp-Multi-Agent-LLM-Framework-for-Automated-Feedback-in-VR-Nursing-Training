import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getSessionDetail } from "../api/backend.js";

export default function SessionDetail() {
  const { studentId, sessionId } = useParams();
  const navigate = useNavigate();

  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Collapse/expand state — all expanded by default
  const [historyOpen, setHistoryOpen] = useState(true);
  const [assessmentOpen, setAssessmentOpen] = useState(true);
  const [cleaningOpen, setCleaningOpen] = useState(true);

  // Per-question explanation expand state
  const [expandedQuestions, setExpandedQuestions] = useState({});

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await getSessionDetail(studentId, sessionId);
        setDetail(data);
      } catch (err) {
        setError(err.response?.data?.detail || err.message || "Failed to load session detail.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [studentId, sessionId]);

  function toggleQuestion(qid) {
    setExpandedQuestions((prev) => ({ ...prev, [qid]: !prev[qid] }));
  }

  const session = detail?.session;
  const history = detail?.steps?.history;
  const assessment = detail?.steps?.assessment;
  const cleaning = detail?.steps?.cleaning_and_dressing;
  const summary = detail?.overall_summary;

  // Score colour helper
  function scoreColor(pct) {
    if (pct >= 70) return "var(--success-text)";
    if (pct >= 50) return "#f5a623";
    return "var(--error-text)";
  }

  return (
    <section className="page-grid">
      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="header-eyebrow">Session Detail</div>
          <h1>{session?.scenario_title || (loading ? "Loading…" : "Session Detail")}</h1>
          <p className="muted" style={{ fontSize: "0.82rem", marginTop: "4px" }}>
            Student: <strong style={{ color: "var(--text-secondary)" }}>{studentId}</strong>
            &nbsp;·&nbsp;Session:{" "}
            <strong style={{ color: "var(--text-secondary)" }}>{sessionId}</strong>
          </p>
        </div>
        <div className="btn-row">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => navigate("/students")}
          >
            ← Back
          </button>
        </div>
      </div>

      {error && <div className="status error">⚠ {error}</div>}

      {loading && (
        <div className="spinner-wrap">
          <div className="spinner" aria-label="Loading" />
        </div>
      )}

      {!loading && detail && (
        <>
          {/* ─── SECTION 1: History Taking ─── */}
          <CollapsibleSection
            title="History Taking"
            open={historyOpen}
            onToggle={() => setHistoryOpen((v) => !v)}
          >
            {history?.evaluated ? (
              <div style={{ display: "grid", gap: "20px" }}>
                {/* Score tiles */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px" }}>
                  {[
                    { label: "Knowledge", value: history?.scores?.knowledge_score },
                    { label: "Communication", value: history?.scores?.communication_score },
                    { label: "Composite", value: history?.scores?.composite_score },
                  ].map(({ label, value }) => (
                    <div
                      key={label}
                      style={{
                        background: "var(--bg-elevated)",
                        borderRadius: "var(--radius-md)",
                        padding: "18px",
                        textAlign: "center",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "2rem",
                          fontWeight: "800",
                          color: "var(--accent)",
                          lineHeight: 1,
                        }}
                      >
                        {value != null ? value : "—"}
                        <span style={{ fontSize: "1rem", fontWeight: "600" }}>/100</span>
                      </div>
                      <div className="section-title" style={{ marginTop: "8px" }}>
                        {label}
                      </div>
                    </div>
                  ))}
                </div>
                {history?.scores?.interpretation && (
                  <p className="muted" style={{ textAlign: "center", fontSize: "0.875rem" }}>
                    {history.scores.interpretation}
                  </p>
                )}

                {/* Communication panel */}
                <div style={{ background: "var(--bg-elevated)", borderRadius: "var(--radius-md)", padding: "18px" }}>
                  <p className="section-title" style={{ marginBottom: "10px" }}>Communication</p>
                  {history?.communication?.verdict && (
                    <span
                      className={`badge ${history.communication.verdict === "Appropriate" ? "badge-success" : "badge-error"}`}
                      style={{ marginBottom: "14px" }}
                    >
                      {history.communication.verdict}
                    </span>
                  )}
                  {(history?.communication?.strengths?.length > 0) && (
                    <div style={{ marginTop: "12px" }}>
                      <p className="section-title" style={{ marginBottom: "6px" }}>Strengths</p>
                      <ul style={{ listStyle: "none", display: "grid", gap: "4px" }}>
                        {history.communication.strengths.map((s, i) => (
                          <li key={i} style={{ color: "var(--success-text)", fontSize: "0.875rem" }}>
                            ✓ {s}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {(history?.communication?.issues_detected?.length > 0) && (
                    <div style={{ marginTop: "12px" }}>
                      <p className="section-title" style={{ marginBottom: "6px" }}>Issues</p>
                      <ul style={{ listStyle: "none", display: "grid", gap: "4px" }}>
                        {history.communication.issues_detected.map((s, i) => (
                          <li key={i} style={{ color: "var(--error-text)", fontSize: "0.875rem" }}>
                            ✗ {s}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Narrated feedback */}
                {history?.narrated_feedback && (
                  <div>
                    <p className="section-title" style={{ marginBottom: "10px" }}>Narrated Feedback</p>
                    <div
                      style={{
                        background: "var(--bg-elevated)",
                        borderLeft: "3px solid var(--accent)",
                        borderRadius: "var(--radius-sm)",
                        padding: "16px 20px",
                        color: "var(--text-secondary)",
                        fontSize: "0.9rem",
                        lineHeight: 1.65,
                      }}
                    >
                      {history.narrated_feedback}
                    </div>
                  </div>
                )}

                {/* Transcript */}
                {history?.conversation?.transcript?.length > 0 && (
                  <div>
                    <p className="section-title" style={{ marginBottom: "10px" }}>Conversation Transcript</p>
                    <div style={{ display: "flex", gap: "16px", marginBottom: "12px", flexWrap: "wrap" }}>
                      {[
                        { label: "Total Turns", value: history.conversation.total_turns },
                        { label: "Student", value: history.conversation.student_turn_count },
                        { label: "Patient", value: history.conversation.patient_turn_count },
                      ].map(({ label, value }) => (
                        <div key={label} style={{ display: "flex", gap: "6px", alignItems: "baseline" }}>
                          <span style={{ fontSize: "1rem", fontWeight: "700", color: "var(--text-primary)" }}>
                            {value ?? "—"}
                          </span>
                          <span className="muted" style={{ fontSize: "0.78rem" }}>{label}</span>
                        </div>
                      ))}
                    </div>
                    <div
                      style={{
                        background: "var(--bg-elevated)",
                        borderRadius: "var(--radius-md)",
                        padding: "16px",
                        maxHeight: "400px",
                        overflowY: "auto",
                        display: "grid",
                        gap: "12px",
                      }}
                    >
                      {history.conversation.transcript.map((turn) => {
                        const isStudent = turn.speaker === "student";
                        return (
                          <div key={turn.turn}>
                            <span
                              style={{
                                fontSize: "0.78rem",
                                fontWeight: "700",
                                color: isStudent ? "var(--accent)" : "var(--text-muted)",
                                textTransform: "uppercase",
                                letterSpacing: "0.05em",
                              }}
                            >
                              {turn.speaker}
                            </span>
                            <p style={{ margin: "3px 0 2px", fontSize: "0.875rem", color: "var(--text-primary)" }}>
                              {turn.text}
                            </p>
                            {turn.timestamp && (
                              <span className="muted" style={{ fontSize: "0.72rem" }}>
                                {new Date(turn.timestamp).toLocaleTimeString()}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="muted">History step not evaluated.</p>
            )}
          </CollapsibleSection>

          {/* ─── SECTION 2: Assessment ─── */}
          <CollapsibleSection
            title="Assessment"
            open={assessmentOpen}
            onToggle={() => setAssessmentOpen((v) => !v)}
          >
            {assessment?.evaluated ? (
              <div style={{ display: "grid", gap: "20px" }}>
                {/* Score summary */}
                <div style={{ display: "flex", gap: "24px", alignItems: "center", flexWrap: "wrap" }}>
                  <div>
                    <span
                      style={{
                        fontSize: "2.2rem",
                        fontWeight: "800",
                        color: "var(--text-primary)",
                      }}
                    >
                      {assessment.correct_count ?? "—"}/{assessment.total_questions ?? "—"}
                    </span>
                    <span className="muted" style={{ marginLeft: "8px", fontSize: "0.875rem" }}>
                      correct
                    </span>
                  </div>
                  {assessment.score_percentage != null && (
                    <div
                      style={{
                        fontSize: "2rem",
                        fontWeight: "800",
                        color: scoreColor(assessment.score_percentage),
                      }}
                    >
                      {assessment.score_percentage}%
                    </div>
                  )}
                </div>

                {/* Questions list */}
                {assessment.questions?.length > 0 && (
                  <div style={{ display: "grid", gap: "10px" }}>
                    {assessment.questions.map((q, idx) => (
                      <div
                        key={q.question_id || idx}
                        style={{
                          background: "var(--bg-elevated)",
                          borderRadius: "var(--radius-md)",
                          padding: "16px",
                          borderLeft: `3px solid ${q.is_correct ? "var(--success-border)" : "var(--error-border)"}`,
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
                          <p style={{ fontWeight: "600", color: "var(--text-primary)", fontSize: "0.9rem" }}>
                            <span className="muted" style={{ marginRight: "8px" }}>Q{idx + 1}.</span>
                            {q.question_text}
                          </p>
                          <span
                            className={`badge ${q.is_correct ? "badge-success" : "badge-error"}`}
                            style={{ flexShrink: 0 }}
                          >
                            {q.is_correct ? "✓ Correct" : "✗ Wrong"}
                          </span>
                        </div>

                        <div style={{ marginTop: "10px", display: "grid", gap: "4px" }}>
                          <p
                            style={{
                              fontSize: "0.875rem",
                              color: q.is_correct ? "var(--success-text)" : "var(--error-text)",
                            }}
                          >
                            Student: {q.student_answer || "—"}
                          </p>
                          {!q.is_correct && (
                            <p style={{ fontSize: "0.875rem", color: "var(--success-text)" }}>
                              Correct: {q.correct_answer || "—"}
                            </p>
                          )}
                        </div>

                        {q.explanation && (
                          <div style={{ marginTop: "10px" }}>
                            <button
                              className="btn btn-ghost btn-sm"
                              onClick={() => toggleQuestion(q.question_id || idx)}
                            >
                              {expandedQuestions[q.question_id || idx] ? "▲ Hide" : "▼ Explanation"}
                            </button>
                            {expandedQuestions[q.question_id || idx] && (
                              <p
                                className="muted"
                                style={{ marginTop: "8px", fontSize: "0.82rem", lineHeight: 1.55 }}
                              >
                                {q.explanation}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <p className="muted">Assessment step not evaluated.</p>
            )}
          </CollapsibleSection>

          {/* ─── SECTION 3: Cleaning & Dressing ─── */}
          <CollapsibleSection
            title="Cleaning & Dressing"
            open={cleaningOpen}
            onToggle={() => setCleaningOpen((v) => !v)}
          >
            {cleaning ? (
              <div style={{ display: "grid", gap: "20px" }}>
                {/* Summary stats row */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "12px" }}>
                  {[
                    {
                      label: "Actions",
                      value: `${cleaning.total_actions_performed ?? "—"}/${cleaning.total_actions_expected ?? "—"}`,
                      accent: true,
                    },
                    {
                      label: "Completion",
                      value: cleaning.completion_percentage != null ? `${cleaning.completion_percentage}%` : "—",
                      accent: true,
                    },
                    {
                      label: "Violations",
                      value: cleaning.sequence_violations ?? "—",
                      color:
                        (cleaning.sequence_violations ?? 0) > 0
                          ? "var(--error-text)"
                          : "var(--success-text)",
                    },
                    {
                      label: "Skipped Mandatory",
                      value: (cleaning.skipped_actions || []).filter((a) => a.is_mandatory).length,
                      color:
                        (cleaning.skipped_actions || []).filter((a) => a.is_mandatory).length > 0
                          ? "var(--error-text)"
                          : "var(--success-text)",
                    },
                  ].map(({ label, value, accent, color }) => (
                    <div
                      key={label}
                      style={{
                        background: "var(--bg-elevated)",
                        borderRadius: "var(--radius-md)",
                        padding: "14px",
                        textAlign: "center",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "1.5rem",
                          fontWeight: "800",
                          lineHeight: 1,
                          color: color || (accent ? "var(--accent)" : "var(--text-primary)"),
                        }}
                      >
                        {value}
                      </div>
                      <div className="section-title" style={{ marginTop: "6px" }}>
                        {label}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Boolean safety flags */}
                <div
                  style={{
                    display: "flex",
                    gap: "18px",
                    flexWrap: "wrap",
                    padding: "14px",
                    background: "var(--bg-elevated)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  {[
                    { label: "Hand Hygiene", value: summary?.cleaning_preparation?.hand_hygiene_compliance },
                    { label: "Solution Verified", value: summary?.cleaning_preparation?.solution_verified },
                    { label: "Dressing Verified", value: summary?.cleaning_preparation?.dressing_verified },
                    { label: "All Actions Done", value: summary?.cleaning_preparation?.all_actions_completed },
                  ].map(({ label, value }) => (
                    <div key={label} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
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
                      <span className="muted" style={{ fontSize: "0.82rem" }}>
                        {label}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Skipped actions */}
                <div>
                  <p className="section-title" style={{ marginBottom: "10px" }}>Skipped Actions</p>
                  {!cleaning.skipped_actions?.length ? (
                    <p className="muted">All actions completed.</p>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      {cleaning.skipped_actions.map((action, idx) => (
                        <div key={idx} style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          {action.is_mandatory ? (
                            <span className="badge badge-error">Mandatory</span>
                          ) : (
                            <span className="muted badge" style={{ border: "1px solid var(--border-subtle)", fontSize: "0.72rem" }}>
                              Optional
                            </span>
                          )}
                          <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                            {action.label || action.action_type}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Action timeline table */}
                {cleaning.action_timeline?.length > 0 && (
                  <div>
                    <p className="section-title" style={{ marginBottom: "10px" }}>Action Timeline</p>
                    <div style={{ overflowX: "auto" }}>
                      <table
                        style={{
                          width: "100%",
                          borderCollapse: "collapse",
                          fontSize: "0.82rem",
                        }}
                      >
                        <thead>
                          <tr style={{ color: "var(--text-muted)", textAlign: "left" }}>
                            {["#", "Action", "Mandatory", "Violation", "Missing Prerequisites", "Time"].map(
                              (col) => (
                                <th
                                  key={col}
                                  style={{
                                    padding: "8px 12px",
                                    fontWeight: "600",
                                    fontSize: "0.72rem",
                                    textTransform: "uppercase",
                                    letterSpacing: "0.06em",
                                    borderBottom: "1px solid var(--border-subtle)",
                                  }}
                                >
                                  {col}
                                </th>
                              )
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {cleaning.action_timeline.map((action) => {
                            const hasViolation = action.prerequisite_violation;
                            const isDuplicate = action.is_duplicate;
                            return (
                              <tr
                                key={action.sequence}
                                style={{
                                  opacity: isDuplicate ? 0.5 : 1,
                                  borderLeft: hasViolation
                                    ? "3px solid var(--error-text)"
                                    : "3px solid transparent",
                                }}
                              >
                                <td
                                  style={{
                                    padding: "10px 12px",
                                    background: "var(--bg-elevated)",
                                    color: "var(--text-muted)",
                                    borderBottom: "1px solid var(--border-subtle)",
                                  }}
                                >
                                  {action.sequence}
                                </td>
                                <td
                                  style={{
                                    padding: "10px 12px",
                                    background: "var(--bg-elevated)",
                                    color: "var(--text-primary)",
                                    borderBottom: "1px solid var(--border-subtle)",
                                  }}
                                >
                                  {action.action_label || action.action_type}
                                </td>
                                <td
                                  style={{
                                    padding: "10px 12px",
                                    background: "var(--bg-elevated)",
                                    borderBottom: "1px solid var(--border-subtle)",
                                    color: action.is_mandatory ? "var(--error-text)" : "var(--text-muted)",
                                  }}
                                >
                                  {action.is_mandatory ? "Yes" : "No"}
                                </td>
                                <td
                                  style={{
                                    padding: "10px 12px",
                                    background: "var(--bg-elevated)",
                                    borderBottom: "1px solid var(--border-subtle)",
                                    color: hasViolation ? "var(--error-text)" : "var(--success-text)",
                                  }}
                                >
                                  {hasViolation ? "⚠ Yes" : "—"}
                                </td>
                                <td
                                  style={{
                                    padding: "10px 12px",
                                    background: "var(--bg-elevated)",
                                    borderBottom: "1px solid var(--border-subtle)",
                                    color: "var(--error-text)",
                                    fontSize: "0.78rem",
                                  }}
                                >
                                  {action.missing_prerequisites?.length
                                    ? action.missing_prerequisites.join(", ")
                                    : "—"}
                                </td>
                                <td
                                  style={{
                                    padding: "10px 12px",
                                    background: "var(--bg-elevated)",
                                    borderBottom: "1px solid var(--border-subtle)",
                                    color: "var(--text-muted)",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {action.timestamp
                                    ? new Date(action.timestamp).toLocaleTimeString()
                                    : "—"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Verification dialogues */}
                <div>
                  <p className="section-title" style={{ marginBottom: "10px" }}>Verification Dialogues</p>
                  {!cleaning.verification_dialogues?.length ? (
                    <p className="muted">No verification recorded.</p>
                  ) : (
                    <div style={{ display: "grid", gap: "12px" }}>
                      {cleaning.verification_dialogues.map((d, idx) => (
                        <div
                          key={idx}
                          style={{
                            background: "var(--bg-elevated)",
                            borderRadius: "var(--radius-md)",
                            padding: "16px",
                          }}
                        >
                          <div style={{ marginBottom: "10px" }}>
                            <span className="badge">{d.material_type || d.action_type}</span>
                          </div>
                          <p style={{ fontSize: "0.875rem", marginBottom: "6px" }}>
                            <span style={{ fontWeight: "700", color: "var(--accent)" }}>Student: </span>
                            <span style={{ color: "var(--text-secondary)" }}>{d.student_said}</span>
                          </p>
                          <p style={{ fontSize: "0.875rem", marginBottom: "8px" }}>
                            <span style={{ fontWeight: "700", color: "var(--text-muted)" }}>Nurse: </span>
                            <span style={{ color: "var(--text-secondary)" }}>{d.nurse_replied}</span>
                          </p>
                          {d.timestamp && (
                            <span className="muted" style={{ fontSize: "0.72rem" }}>
                              {new Date(d.timestamp).toLocaleTimeString()}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Critical safety concerns */}
                <div>
                  <p className="section-title" style={{ marginBottom: "10px" }}>Critical Safety Concerns</p>
                  {!summary?.critical_safety_concerns?.length ? (
                    <span className="badge badge-success">✓ No critical safety concerns</span>
                  ) : (
                    <div style={{ display: "grid", gap: "8px" }}>
                      {summary.critical_safety_concerns.map((concern, idx) => (
                        <div key={idx} className="status error">
                          ⚠ {concern}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <p className="muted">Cleaning and dressing data not available.</p>
            )}
          </CollapsibleSection>
        </>
      )}

      {!loading && !detail && !error && (
        <p className="muted">Session data not found.</p>
      )}
    </section>
  );
}

function CollapsibleSection({ title, open, onToggle, children }) {
  return (
    <div className="panel" style={{ padding: 0, overflow: "visible" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "20px 24px",
          borderBottom: open ? "1px solid var(--border-subtle)" : "none",
        }}
      >
        <h2 style={{ fontSize: "1.05rem", margin: 0 }}>{title}</h2>
        <button className="btn btn-ghost btn-sm" onClick={onToggle}>
          {open ? "▲ Collapse" : "▼ Expand"}
        </button>
      </div>
      {open && <div style={{ padding: "24px" }}>{children}</div>}
    </div>
  );
}
