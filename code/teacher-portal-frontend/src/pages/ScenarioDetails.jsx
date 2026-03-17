import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ScenarioForm from "../components/ScenarioForm.jsx";
import { getScenarioById } from "../api/backend.js";

export default function ScenarioDetails() {
  const { scenarioId } = useParams();
  const navigate = useNavigate();
  const [scenario, setScenario] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadScenario() {
      setLoading(true);
      setError("");
      try {
        const data = await getScenarioById(scenarioId);
        setScenario(data);
      } catch (err) {
        setError(err.response?.data?.detail || err.message || "Failed to load scenario.");
      } finally {
        setLoading(false);
      }
    }
    loadScenario();
  }, [scenarioId]);

  return (
    <section className="page-grid">
      <div className="page-header">
        <div>
          <div className="header-eyebrow">Scenario</div>
          <h1>Scenario Details</h1>
          <p>Review the scenario in read-only clinical form layout.</p>
        </div>
        {scenario && (
          <button
            className="btn btn-primary"
            onClick={() => navigate(`/scenarios/${scenarioId}/edit`)}
          >
            Edit Scenario
          </button>
        )}
      </div>

      {error && <div className="status error">{error}</div>}

      {loading ? (
        <div className="spinner-wrap">
          <div className="spinner" aria-label="Loading" />
        </div>
      ) : (
        scenario && <ScenarioForm scenarioData={scenario} mode="view" />
      )}
    </section>
  );
}
