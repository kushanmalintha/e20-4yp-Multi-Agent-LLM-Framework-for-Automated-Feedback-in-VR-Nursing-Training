const OPTION_LABELS = ["A", "B", "C", "D"];

function QuestionCard({ question, index, readOnly, onQuestionChange, onOptionChange, onDelete, errors }) {
  return (
    <div className="panel" style={{ background: "var(--bg-elevated)", borderColor: "var(--border-medium)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <span className="section-title">Question {index + 1}</span>
        {!readOnly && (
          <button type="button" className="btn btn-danger btn-sm" onClick={onDelete}>
            Delete
          </button>
        )}
      </div>

      <div style={{ display: "grid", gap: "16px" }}>
        <div className="field">
          <label>Question text</label>
          <input
            value={question.question || ""}
            readOnly={readOnly}
            onChange={(e) => onQuestionChange("question", e.target.value)}
            placeholder="Enter the question…"
          />
        </div>

        <div className="form-grid">
          {OPTION_LABELS.map((label, optionIndex) => (
            <div className="field" key={`${question.id || index}-${label}`}>
              <label>Option {label}</label>
              <input
                value={question.options?.[optionIndex] || ""}
                readOnly={readOnly}
                onChange={(e) => onOptionChange(optionIndex, e.target.value)}
                placeholder={`Option ${label}`}
                style={errors[`question_${index}_options`] ? { borderColor: "var(--error-text)" } : {}}
              />
            </div>
          ))}
        </div>

        {errors[`question_${index}_options`] && (
          <span style={{ color: "var(--error-text)", fontSize: "0.8rem" }}>
            {errors[`question_${index}_options`]}
          </span>
        )}

        <div className="form-grid">
          <div className="field">
            <label>Correct Answer</label>
            <select
              value={question.correct_answer || "A"}
              disabled={readOnly}
              onChange={(e) => onQuestionChange("correct_answer", e.target.value)}
              style={errors[`question_${index}_correct_answer`] ? { borderColor: "var(--error-text)" } : {}}
            >
              {OPTION_LABELS.map((label) => (
                <option key={label} value={label}>{label}</option>
              ))}
            </select>
            {errors[`question_${index}_correct_answer`] && (
              <span style={{ color: "var(--error-text)", fontSize: "0.8rem" }}>
                {errors[`question_${index}_correct_answer`]}
              </span>
            )}
          </div>
          <div className="field" style={{ gridColumn: "span 1" }}>
            <label>Explanation</label>
            <textarea
              value={question.explanation || ""}
              readOnly={readOnly}
              onChange={(e) => onQuestionChange("explanation", e.target.value)}
              placeholder="Why is this the correct answer?"
              style={{ minHeight: "80px" }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AssessmentQuestionsForm({
  questions,
  readOnly,
  errors,
  onAddQuestion,
  onDeleteQuestion,
  onQuestionChange,
  onOptionChange,
}) {
  return (
    <div className="panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px" }}>
        <div>
          <h3>Assessment Questions</h3>
          {errors.assessment_questions && (
            <span style={{ color: "var(--error-text)", fontSize: "0.8rem" }}>
              {errors.assessment_questions}
            </span>
          )}
        </div>
        {!readOnly && (
          <button type="button" className="btn btn-primary btn-sm" onClick={onAddQuestion}>
            + Add Question
          </button>
        )}
      </div>

      <div style={{ display: "grid", gap: "16px" }}>
        {questions.map((question, index) => (
          <QuestionCard
            key={question.id || `question-${index}`}
            question={question}
            index={index}
            readOnly={readOnly}
            errors={errors}
            onDelete={() => onDeleteQuestion(index)}
            onQuestionChange={(field, value) => onQuestionChange(index, field, value)}
            onOptionChange={(optionIndex, value) => onOptionChange(index, optionIndex, value)}
          />
        ))}
      </div>
    </div>
  );
}
