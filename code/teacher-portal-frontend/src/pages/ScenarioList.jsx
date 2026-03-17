import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import ScenarioCard from "../components/ScenarioCard.jsx";
import { getScenarios } from "../api/backend.js";

export default function ScenarioList() {
  const navigate = useNavigate();
  const [scenarios, setScenarios] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleLoadScenarios() {
    setLoading(true);
    setError("");
    try {
      const data = await getScenarios();
      setScenarios(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to load scenarios");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    handleLoadScenarios();
  }, []);

  return (
    <section className="page-grid">
      <div className="page-header">
        <div>
          <div className="header-eyebrow">Library</div>
          <h1>Scenario List</h1>
          <p>Browse saved scenarios, view details, or launch a VR session.</p>
        </div>
        <div className="btn-row">
          <button className="btn btn-secondary" onClick={handleLoadScenarios} disabled={loading}>
            {loading ? "Loading…" : "↺ Refresh"}
          </button>
          <button className="btn btn-primary" onClick={() => navigate("/scenarios/create")}>
            + New Scenario
          </button>
        </div>
      </div>

      {error && <div className="status error">{error}</div>}

      {loading ? (
        <div className="spinner-wrap">
          <div className="spinner" aria-label="Loading" />
        </div>
      ) : (
        <div className="scenario-list">
          {scenarios.length === 0 ? (
            <div className="panel">
              <p className="muted">No scenarios loaded yet. Use Refresh to query the backend.</p>
            </div>
          ) : (
            scenarios.map((scenario) => (
              <ScenarioCard
                key={scenario.scenario_id}
                scenario={scenario}
                onView={() => navigate(`/scenarios/${scenario.scenario_id}`)}
                onEdit={() => navigate(`/scenarios/${scenario.scenario_id}/edit`)}
                onStart={() =>
                  navigate("/sessions/start", {
                    state: { scenarioId: scenario.scenario_id },
                  })
                }
              />
            ))
          )}
        </div>
      )}
    </section>
  );
}
