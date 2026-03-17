const WOUND_FIELDS = [
  { key: "wound_type",      label: "Wound Type",       placeholder: "e.g. Surgical incision" },
  { key: "location",        label: "Location",          placeholder: "e.g. Abdomen, lower" },
  { key: "size",            label: "Size",              placeholder: "e.g. 8 cm" },
  { key: "appearance",      label: "Appearance",        placeholder: "e.g. Clean, granulating" },
  { key: "wound_age",       label: "Wound Age",         placeholder: "e.g. Post-op Day 3" },
  { key: "suture_type",     label: "Suture Type",       placeholder: "e.g. Absorbable, interrupted" },
  { key: "expected_healing",label: "Expected Healing",  placeholder: "e.g. 2–3 weeks" },
  { key: "dressing_status", label: "Dressing Status",   placeholder: "e.g. Changed yesterday" },
];

export default function WoundDetailsForm({ data, readOnly, onFieldChange }) {
  return (
    <div className="panel">
      <h3 style={{ marginBottom: "20px" }}>Wound Details</h3>
      <div className="form-grid">
        {WOUND_FIELDS.map(({ key, label, placeholder }) => (
          <div className="field" key={key}>
            <label>{label}</label>
            <input
              value={data[key] || ""}
              readOnly={readOnly}
              onChange={(e) => onFieldChange(key, e.target.value)}
              placeholder={placeholder}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
