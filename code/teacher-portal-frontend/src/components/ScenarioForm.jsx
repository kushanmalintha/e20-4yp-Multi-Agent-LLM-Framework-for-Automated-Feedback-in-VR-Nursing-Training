import { useEffect, useMemo, useState } from "react";

import AssessmentQuestionsForm from "./AssessmentQuestionsForm.jsx";
import PatientHistoryForm from "./PatientHistoryForm.jsx";
import WoundDetailsForm from "./WoundDetailsForm.jsx";

const EMPTY_SCENARIO = {
  scenario_id: "",
  scenario_title: "",
  description: "",
  created_by: "teacher_portal",
  created_at: "",
  updated_at: "",
  vector_store_namespace: "",
  patient_history: {
    name: "",
    age: "",
    gender: "",
    address: "",
    allergies: [],
    current_medications: [],
    medical_history: [],
    surgery_details: {
      procedure: "",
      hospital: "",
      surgeon: "",
      date: "",
      reason: "",
    },
    pain_level: {
      pain_score: "",
      description: "",
      pain_medication: "",
      last_pain_medication: "",
    },
    comfort_needs: {
      needs_water: false,
      needs_bathroom: false,
      comfortable_to_proceed: true,
      current_position: "",
    },
  },
  wound_details: {
    wound_type: "",
    location: "",
    size: "",
    appearance: "",
    wound_age: "",
    suture_type: "",
    expected_healing: "",
    dressing_status: "",
  },
  assessment_questions: [
    {
      id: "q1",
      question: "",
      options: ["", "", "", ""],
      correct_answer: "A",
      explanation: "",
    },
  ],
};

function mergeDeep(base, value) {
  if (Array.isArray(base)) return Array.isArray(value) ? value : base;
  if (typeof base !== "object" || base === null) return value ?? base;
  const output = { ...base, ...(value || {}) };
  for (const key of Object.keys(base)) {
    output[key] = mergeDeep(base[key], value?.[key]);
  }
  return output;
}

function buildInitialState(scenarioData) {
  const merged = mergeDeep(EMPTY_SCENARIO, scenarioData || {});
  merged.description = merged.description || "";
  merged.vector_store_namespace = merged.vector_store_namespace || merged.scenario_id || "";
  return merged;
}

function setNestedValue(target, path, value) {
  const keys = path.split(".");
  const clone = structuredClone(target);
  let pointer = clone;
  for (let i = 0; i < keys.length - 1; i += 1) pointer = pointer[keys[i]];
  pointer[keys[keys.length - 1]] = value;
  return clone;
}

function validate(formData) {
  const nextErrors = {};
  if (!formData.scenario_id.trim()) nextErrors.scenario_id = "Scenario ID is required.";
  if (!formData.scenario_title.trim()) nextErrors.scenario_title = "Scenario title is required.";
  if (!formData.patient_history.name.trim()) nextErrors.patient_name = "Patient name is required.";
  if (!formData.assessment_questions.length) nextErrors.assessment_questions = "At least one question is required.";

  formData.assessment_questions.forEach((question, index) => {
    const optionCount = (question.options || []).filter((o) => o.trim()).length;
    if (optionCount !== 4) nextErrors[`question_${index}_options`] = "Each question must have 4 options.";
    const correctIndex = ["A", "B", "C", "D"].indexOf(question.correct_answer);
    if (correctIndex === -1 || !question.options?.[correctIndex]?.trim()) {
      nextErrors[`question_${index}_correct_answer`] = "Correct answer must match a populated option.";
    }
  });

  return nextErrors;
}

function normalizeForSubmit(formData) {
  const normalized = structuredClone(formData);
  normalized.scenario_id = normalized.scenario_id.trim();
  normalized.scenario_title = normalized.scenario_title.trim();
  normalized.description = normalized.description.trim();
  normalized.vector_store_namespace = normalized.vector_store_namespace.trim() || normalized.scenario_id;
  normalized.patient_history.age = normalized.patient_history.age === "" ? "" : Number(normalized.patient_history.age);
  normalized.patient_history.pain_level.pain_score =
    normalized.patient_history.pain_level.pain_score === "" ? "" : Number(normalized.patient_history.pain_level.pain_score);
  normalized.assessment_questions = normalized.assessment_questions.map((q, i) => ({
    ...q,
    id: q.id?.trim() || `q${i + 1}`,
    question: q.question.trim(),
    explanation: q.explanation.trim(),
    options: q.options.map((o) => o.trim()),
  }));
  return normalized;
}

export default function ScenarioForm({ scenarioData, onSubmit, mode = "create", submitLabel }) {
  const readOnly = mode === "view";
  const [formData, setFormData] = useState(() => buildInitialState(scenarioData));
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");

  useEffect(() => {
    setFormData(buildInitialState(scenarioData));
    setErrors({});
    setFormError("");
  }, [scenarioData]);

  const computedSubmitLabel = useMemo(() => {
    if (submitLabel) return submitLabel;
    return mode === "edit" ? "Save Changes" : "Create Scenario";
  }, [mode, submitLabel]);

  function handleScenarioFieldChange(field, value) {
    setFormData((current) => {
      const next = { ...current, [field]: value };
      if (field === "scenario_id" && !current.vector_store_namespace) next.vector_store_namespace = value;
      return next;
    });
  }

  function handlePatientFieldChange(path, value) {
    setFormData((current) => ({
      ...current,
      patient_history: setNestedValue(current.patient_history, path, value),
    }));
  }

  function handlePatientListChange(field, index, value) {
    setFormData((current) => {
      const nextItems = [...current.patient_history[field]];
      nextItems[index] = value;
      return { ...current, patient_history: { ...current.patient_history, [field]: nextItems } };
    });
  }

  function handlePatientListAdd(field) {
    setFormData((current) => ({
      ...current,
      patient_history: { ...current.patient_history, [field]: [...current.patient_history[field], ""] },
    }));
  }

  function handlePatientListRemove(field, index) {
    setFormData((current) => ({
      ...current,
      patient_history: {
        ...current.patient_history,
        [field]: current.patient_history[field].filter((_, i) => i !== index),
      },
    }));
  }

  function handleWoundFieldChange(field, value) {
    setFormData((current) => ({ ...current, wound_details: { ...current.wound_details, [field]: value } }));
  }

  function handleQuestionChange(index, field, value) {
    setFormData((current) => ({
      ...current,
      assessment_questions: current.assessment_questions.map((q, i) =>
        i === index ? { ...q, [field]: value } : q
      ),
    }));
  }

  function handleQuestionOptionChange(questionIndex, optionIndex, value) {
    setFormData((current) => ({
      ...current,
      assessment_questions: current.assessment_questions.map((q, i) => {
        if (i !== questionIndex) return q;
        const nextOptions = [...q.options];
        nextOptions[optionIndex] = value;
        return { ...q, options: nextOptions };
      }),
    }));
  }

  function handleAddQuestion() {
    setFormData((current) => ({
      ...current,
      assessment_questions: [
        ...current.assessment_questions,
        { id: `q${current.assessment_questions.length + 1}`, question: "", options: ["", "", "", ""], correct_answer: "A", explanation: "" },
      ],
    }));
  }

  function handleDeleteQuestion(index) {
    setFormData((current) => ({
      ...current,
      assessment_questions: current.assessment_questions.filter((_, i) => i !== index),
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (readOnly || !onSubmit) return;
    const nextErrors = validate(formData);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      setFormError("Resolve the validation errors before saving.");
      return;
    }
    setFormError("");
    await onSubmit(normalizeForSubmit(formData));
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: "24px" }}>
      {formError && <div className="status error">{formError}</div>}

      {/* ── Scenario Info ── */}
      <div className="panel">
        <h3 style={{ marginBottom: "20px" }}>Scenario Information</h3>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="sf-id">Scenario ID *</label>
            <input
              id="sf-id"
              value={formData.scenario_id}
              readOnly={readOnly || mode === "edit"}
              onChange={(e) => handleScenarioFieldChange("scenario_id", e.target.value)}
              placeholder="e.g. scenario_wound_01"
              required
              style={errors.scenario_id ? { borderColor: "var(--error-text)" } : {}}
            />
            {errors.scenario_id && <span style={{ color: "var(--error-text)", fontSize: "0.8rem" }}>{errors.scenario_id}</span>}
          </div>

          <div className="field">
            <label htmlFor="sf-title">Scenario Title *</label>
            <input
              id="sf-title"
              value={formData.scenario_title}
              readOnly={readOnly}
              onChange={(e) => handleScenarioFieldChange("scenario_title", e.target.value)}
              placeholder="e.g. Post-op Wound Assessment"
              required
              style={errors.scenario_title ? { borderColor: "var(--error-text)" } : {}}
            />
            {errors.scenario_title && <span style={{ color: "var(--error-text)", fontSize: "0.8rem" }}>{errors.scenario_title}</span>}
          </div>

          <div className="field">
            <label htmlFor="sf-created-by">Created By</label>
            <input id="sf-created-by" value={formData.created_by} readOnly={readOnly} onChange={(e) => handleScenarioFieldChange("created_by", e.target.value)} />
          </div>

          <div className="field">
            <label htmlFor="sf-namespace">Vector Store Namespace</label>
            <input id="sf-namespace" value={formData.vector_store_namespace} readOnly={readOnly} onChange={(e) => handleScenarioFieldChange("vector_store_namespace", e.target.value)} placeholder="Auto-filled from Scenario ID" />
          </div>

          <div className="field" style={{ gridColumn: "1 / -1" }}>
            <label htmlFor="sf-description">Description</label>
            <textarea id="sf-description" value={formData.description} readOnly={readOnly} onChange={(e) => handleScenarioFieldChange("description", e.target.value)} placeholder="Brief description of this clinical scenario…" style={{ minHeight: "80px" }} />
          </div>

          {mode !== "create" && (
            <>
              <div className="field">
                <label>Created At</label>
                <input value={formData.created_at || ""} readOnly />
              </div>
              <div className="field">
                <label>Updated At</label>
                <input value={formData.updated_at || ""} readOnly />
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Sub-forms ── */}
      <PatientHistoryForm
        data={formData.patient_history}
        readOnly={readOnly}
        errors={errors}
        onFieldChange={handlePatientFieldChange}
        onListChange={handlePatientListChange}
        onListAdd={handlePatientListAdd}
        onListRemove={handlePatientListRemove}
      />

      <WoundDetailsForm
        data={formData.wound_details}
        readOnly={readOnly}
        onFieldChange={handleWoundFieldChange}
      />

      <AssessmentQuestionsForm
        questions={formData.assessment_questions}
        readOnly={readOnly}
        errors={errors}
        onAddQuestion={handleAddQuestion}
        onDeleteQuestion={handleDeleteQuestion}
        onQuestionChange={handleQuestionChange}
        onOptionChange={handleQuestionOptionChange}
      />

      {!readOnly && (
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button type="submit" className="btn btn-primary btn-lg">
            {computedSubmitLabel}
          </button>
        </div>
      )}
    </form>
  );
}
