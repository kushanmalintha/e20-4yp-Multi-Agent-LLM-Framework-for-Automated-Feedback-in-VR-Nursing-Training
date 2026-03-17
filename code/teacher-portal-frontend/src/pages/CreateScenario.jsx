import { useState } from "react";
import ScenarioForm from "../components/ScenarioForm.jsx";
import { createScenario } from "../api/backend.js";

export default function CreateScenario() {
  const [status, setStatus] = useState({ type: "", message: "" });

  async function handleCreate(formData) {
    try {
      const response = await createScenario({
        scenario_id: formData.scenario_id,
        title: formData.scenario_title,
        description: formData.description || formData.scenario_title,
        scenario_data: formData,
      });
      setStatus({
        type: "success",
        message: response.message || "Scenario created successfully.",
      });
    } catch (err) {
      setStatus({
        type: "error",
        message: err.response?.data?.detail || err.message || "Failed to create scenario.",
      });
    }
  }

  return (
    <section className="page-grid">
      <div className="page-header">
        <div>
          <div className="header-eyebrow">Scenario</div>
          <h1>Create Scenario</h1>
          <p>Use the structured clinical form instead of editing raw scenario JSON.</p>
        </div>
      </div>

      {status.message && (
        <div className={`status ${status.type}`}>{status.message}</div>
      )}

      <ScenarioForm mode="create" onSubmit={handleCreate} />
    </section>
  );
}
