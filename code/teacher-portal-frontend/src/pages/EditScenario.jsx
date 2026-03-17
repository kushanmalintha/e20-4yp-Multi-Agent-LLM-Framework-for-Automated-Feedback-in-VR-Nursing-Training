import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ScenarioForm from "../components/ScenarioForm.jsx";
import { getScenarioById, updateScenario } from "../api/backend.js";

export default function EditScenario() {
  const { scenarioId } = useParams();
  const [scenario, setScenario] = useState(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState({ type: "", message: "" });

  useEffect(() => {
    async function loadScenario() {
      setLoading(true);
      try {
        const data = await getScenarioById(scenarioId);
        setScenario(data);
      } catch (err) {
        setStatus({
          type: "error",
          message: err.response?.data?.detail || err.message || "Failed to load scenario.",
        });
      } finally {
        setLoading(false);
      }
    }
    loadScenario();
  }, [scenarioId]);

  async function handleUpdate(formData) {
    try {
      const response = await updateScenario({
        scenario_id: formData.scenario_id,
        title: formData.scenario_title,
        description: formData.description || formData.scenario_title,
        scenario_data: formData,
      });
      setStatus({
        type: "success",
        message: response.message || "Scenario updated successfully.",
      });
      setScenario(formData);
    } catch (err) {
      setStatus({
        type: "error",
        message: err.response?.data?.detail || err.message || "Failed to update scenario.",
      });
    }
  }

  return (
    <section className="page-grid">
      <div className="page-header">
        <div>
          <div className="header-eyebrow">Scenario</div>
          <h1>Edit Scenario</h1>
          <p>Update the structured scenario form and save it back to Firestore.</p>
        </div>
      </div>

      {status.message && (
        <div className={`status ${status.type}`}>{status.message}</div>
      )}

      {loading ? (
        <div className="spinner-wrap">
          <div className="spinner" aria-label="Loading" />
        </div>
      ) : (
        scenario && (
          <ScenarioForm
            scenarioData={scenario}
            mode="edit"
            onSubmit={handleUpdate}
            submitLabel="Update Scenario"
          />
        )
      )}
    </section>
  );
}
