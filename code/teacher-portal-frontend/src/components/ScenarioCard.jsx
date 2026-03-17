export default function ScenarioCard({ scenario, onView, onEdit, onStart }) {
  return (
    <article className="card">
      <div className="scenario-card-header">
        <div>
          <span className="scenario-meta">{scenario.scenario_id}</span>
          <h3 style={{ marginTop: "10px" }}>{scenario.title || "Untitled Scenario"}</h3>
        </div>
        <span className="badge badge-success">✓ Ready for VR</span>
      </div>

      {scenario.description && (
        <p className="muted" style={{ fontSize: "0.875rem", marginTop: "8px" }}>
          {scenario.description}
        </p>
      )}

      <div className="btn-row" style={{ marginTop: "20px", paddingTop: "16px", borderTop: "1px solid var(--border-subtle)" }}>
        <button className="btn btn-secondary btn-sm" onClick={onView}>
          View
        </button>
        <button className="btn btn-secondary btn-sm" onClick={onEdit}>
          Edit
        </button>
        <button className="btn btn-primary btn-sm" onClick={onStart}>
          Start Session
        </button>
      </div>
    </article>
  );
}
