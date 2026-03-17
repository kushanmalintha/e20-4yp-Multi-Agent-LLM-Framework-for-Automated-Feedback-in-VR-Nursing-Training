function ArrayField({ label, items, onAdd, onRemove, onChange, readOnly = false }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      <span className="section-title">{label}</span>
      {items.map((item, index) => (
        <div key={`${label}-${index}`} style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <input
            className="field"
            style={{ flex: 1, padding: "10px 14px", background: "var(--bg-elevated)", border: "1px solid var(--border-medium)", borderRadius: "var(--radius-md)", color: "var(--text-primary)", fontSize: "0.875rem" }}
            value={item}
            readOnly={readOnly}
            onChange={(e) => onChange(index, e.target.value)}
            placeholder={`${label} item`}
          />
          {!readOnly && (
            <button type="button" className="btn btn-danger btn-sm" onClick={() => onRemove(index)}>
              ✕
            </button>
          )}
        </div>
      ))}
      {!readOnly && (
        <button type="button" className="btn btn-ghost btn-sm" style={{ alignSelf: "flex-start" }} onClick={onAdd}>
          + Add Item
        </button>
      )}
    </div>
  );
}

export default function PatientHistoryForm({
  data,
  readOnly,
  errors,
  onFieldChange,
  onListChange,
  onListAdd,
  onListRemove,
}) {
  const surgery = data.surgery_details || {};
  const pain = data.pain_level || {};
  const comfort = data.comfort_needs || {};

  return (
    <div className="panel">
      <h3 style={{ marginBottom: "20px" }}>Patient History</h3>

      <div className="form-grid" style={{ marginBottom: "20px" }}>
        <div className="field">
          <label htmlFor="ph-name">Name *</label>
          <input
            id="ph-name"
            value={data.name || ""}
            readOnly={readOnly}
            onChange={(e) => onFieldChange("name", e.target.value)}
            placeholder="Patient full name"
            required
          />
          {errors.patient_name && <span style={{ color: "var(--error-text)", fontSize: "0.8rem" }}>{errors.patient_name}</span>}
        </div>
        <div className="field">
          <label htmlFor="ph-age">Age</label>
          <input id="ph-age" type="number" value={data.age ?? ""} readOnly={readOnly} onChange={(e) => onFieldChange("age", e.target.value)} placeholder="e.g. 45" />
        </div>
        <div className="field">
          <label htmlFor="ph-gender">Gender</label>
          <input id="ph-gender" value={data.gender || ""} readOnly={readOnly} onChange={(e) => onFieldChange("gender", e.target.value)} placeholder="e.g. Female" />
        </div>
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label htmlFor="ph-address">Address</label>
          <input id="ph-address" value={data.address || ""} readOnly={readOnly} onChange={(e) => onFieldChange("address", e.target.value)} placeholder="Street, City, Country" />
        </div>
      </div>

      <div style={{ display: "grid", gap: "20px", marginBottom: "20px" }}>
        <ArrayField
          label="Allergies"
          items={data.allergies || []}
          readOnly={readOnly}
          onAdd={() => onListAdd("allergies")}
          onRemove={(i) => onListRemove("allergies", i)}
          onChange={(i, v) => onListChange("allergies", i, v)}
        />
        <ArrayField
          label="Current Medications"
          items={data.current_medications || []}
          readOnly={readOnly}
          onAdd={() => onListAdd("current_medications")}
          onRemove={(i) => onListRemove("current_medications", i)}
          onChange={(i, v) => onListChange("current_medications", i, v)}
        />
        <ArrayField
          label="Medical History"
          items={data.medical_history || []}
          readOnly={readOnly}
          onAdd={() => onListAdd("medical_history")}
          onRemove={(i) => onListRemove("medical_history", i)}
          onChange={(i, v) => onListChange("medical_history", i, v)}
        />
      </div>

      <div className="divider" style={{ margin: "24px 0" }} />
      <p className="section-title" style={{ marginBottom: "12px" }}>Surgery Details</p>
      <div className="form-grid" style={{ marginBottom: "20px" }}>
        {[
          ["surgery_details.procedure", "Procedure", surgery.procedure, "e.g. Laparotomy"],
          ["surgery_details.hospital", "Hospital", surgery.hospital, "Hospital name"],
          ["surgery_details.surgeon", "Surgeon", surgery.surgeon, "Surgeon name"],
          ["surgery_details.reason", "Reason", surgery.reason, "Reason for surgery"],
        ].map(([path, label, value, placeholder]) => (
          <div className="field" key={path}>
            <label>{label}</label>
            <input value={value || ""} readOnly={readOnly} onChange={(e) => onFieldChange(path, e.target.value)} placeholder={placeholder} />
          </div>
        ))}
        <div className="field">
          <label>Date</label>
          <input type="date" value={surgery.date || ""} readOnly={readOnly} onChange={(e) => onFieldChange("surgery_details.date", e.target.value)} />
        </div>
      </div>

      <div className="divider" style={{ margin: "24px 0" }} />
      <p className="section-title" style={{ marginBottom: "12px" }}>Pain Level</p>
      <div className="form-grid" style={{ marginBottom: "20px" }}>
        <div className="field">
          <label>Pain Score (0–10)</label>
          <input type="number" min="0" max="10" value={pain.pain_score ?? ""} readOnly={readOnly} onChange={(e) => onFieldChange("pain_level.pain_score", e.target.value)} placeholder="e.g. 6" />
        </div>
        <div className="field">
          <label>Pain Description</label>
          <input value={pain.description || ""} readOnly={readOnly} onChange={(e) => onFieldChange("pain_level.description", e.target.value)} placeholder="Throbbing, sharp…" />
        </div>
        <div className="field">
          <label>Medication</label>
          <input value={pain.pain_medication || ""} readOnly={readOnly} onChange={(e) => onFieldChange("pain_level.pain_medication", e.target.value)} placeholder="e.g. Paracetamol" />
        </div>
        <div className="field">
          <label>Last Medication Time</label>
          <input value={pain.last_pain_medication || ""} readOnly={readOnly} onChange={(e) => onFieldChange("pain_level.last_pain_medication", e.target.value)} placeholder="e.g. 2 hours ago" />
        </div>
      </div>

      <div className="divider" style={{ margin: "24px 0" }} />
      <p className="section-title" style={{ marginBottom: "12px" }}>Comfort Needs</p>
      <div className="form-grid">
        <div className="field">
          <label>Current Position</label>
          <input value={comfort.current_position || ""} readOnly={readOnly} onChange={(e) => onFieldChange("comfort_needs.current_position", e.target.value)} placeholder="e.g. Supine" />
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "20px", alignItems: "center", paddingTop: "28px" }}>
          {[
            ["comfort_needs.needs_water", "Needs Water", !!comfort.needs_water],
            ["comfort_needs.needs_bathroom", "Needs Bathroom", !!comfort.needs_bathroom],
            ["comfort_needs.comfortable_to_proceed", "Comfortable to Proceed", !!comfort.comfortable_to_proceed],
          ].map(([path, label, checked]) => (
            <label key={path} style={{ display: "flex", alignItems: "center", gap: "8px", cursor: readOnly ? "default" : "pointer", color: "var(--text-secondary)", fontSize: "0.875rem" }}>
              <input
                type="checkbox"
                checked={checked}
                disabled={readOnly}
                onChange={(e) => onFieldChange(path, e.target.checked)}
                style={{ accentColor: "var(--accent)", width: "16px", height: "16px" }}
              />
              {label}
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
