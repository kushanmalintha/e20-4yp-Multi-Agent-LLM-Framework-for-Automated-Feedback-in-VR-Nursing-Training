import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { getScenarios, startSession } from "../api/backend.js";

export default function StartSession() {
  const location = useLocation();
  const preselectedScenarioId = location.state?.scenarioId || "";

  const [scenarios, setScenarios] = useState([]);
  const [form, setForm] = useState({
    scenario_id: preselectedScenarioId,
    student_id: "",
  });
  const [status, setStatus] = useState({ type: "", message: "" });
  const [loadingScenarios, setLoadingScenarios] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    async function loadScenarioOptions() {
      setLoadingScenarios(true);
      try {
        const data = await getScenarios();
        setScenarios(data);
      } catch (err) {
        setStatus({
          type: "error",
          message: err.response?.data?.detail || err.message || "Failed to load scenarios",
        });
      } finally {
        setLoadingScenarios(false);
      }
    }

    loadScenarioOptions();
  }, []);

  useEffect(() => {
    if (preselectedScenarioId) {
      setForm((current) => ({ ...current, scenario_id: preselectedScenarioId }));
    }
  }, [preselectedScenarioId]);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setStatus({ type: "", message: "" });

    try {
      const response = await startSession({
        scenario_id: form.scenario_id,
        student_id: form.student_id.trim(),
      });
      setStatus({
        type: "success",
        message: `Session started successfully. Session ID: ${response.session_id}`,
      });
    } catch (err) {
      setStatus({
        type: "error",
        message: err.response?.data?.detail || err.message || "Failed to start session",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="page-grid">
      <div className="page-header">
        <div>
          <h1>Start Session</h1>
          <p>Launch a VR session for one student. Unity will detect it through `/session/active`.</p>
        </div>
      </div>

      {status.message && <div className={`status ${status.type}`}>{status.message}</div>}

      <form className="panel page-grid" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="scenario_id">Select Scenario</label>
          <select
            id="scenario_id"
            value={form.scenario_id}
            onChange={(event) =>
              setForm((current) => ({ ...current, scenario_id: event.target.value }))
            }
            required
          >
            <option value="">{loadingScenarios ? "Loading..." : "Choose a scenario"}</option>
            {scenarios.map((scenario) => (
              <option key={scenario.scenario_id} value={scenario.scenario_id}>
                {scenario.scenario_id} - {scenario.title}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="student_id">Student ID</label>
          <input
            id="student_id"
            value={form.student_id}
            onChange={(event) =>
              setForm((current) => ({ ...current, student_id: event.target.value }))
            }
            placeholder="student_001"
            required
          />
        </div>

        <div className="button-row">
          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Starting..." : "Start Session"}
          </button>
        </div>
      </form>
    </section>
  );
}
