import { Link } from "react-router-dom";

const cards = [
  {
    icon: "🔬",
    title: "Create Scenario",
    description: "Build a new clinical scenario and store the runtime-compatible metadata in Firestore.",
    to: "/scenarios/create",
    action: "Open Builder",
  },
  {
    icon: "📋",
    title: "View Scenarios",
    description: "Review saved scenarios, open the structured viewer, and launch VR sessions for students.",
    to: "/scenarios",
    action: "Browse Scenarios",
  },
  {
    icon: "📄",
    title: "Upload Guidelines",
    description: "Send clinical guideline .txt files to the shared OpenAI vector store used by the backend.",
    to: "/guidelines/upload",
    action: "Upload File",
  },
];

export default function Dashboard() {
  return (
    <section className="page-grid">
      <div className="page-header">
        <div>
          <div className="header-eyebrow">Overview</div>
          <h1>Teacher Dashboard</h1>
          <p>Manage scenarios, launch VR sessions, and update clinical retrieval guidelines.</p>
        </div>
      </div>

      <div className="page-grid dashboard-grid">
        {cards.map((card) => (
          <article key={card.title} className="card dashboard-card">
            <div className="dashboard-card-icon" aria-hidden="true">{card.icon}</div>
            <h3>{card.title}</h3>
            <p>{card.description}</p>
            <div className="card-footer">
              <Link className="btn btn-primary btn-sm" to={card.to}>
                {card.action}
              </Link>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
