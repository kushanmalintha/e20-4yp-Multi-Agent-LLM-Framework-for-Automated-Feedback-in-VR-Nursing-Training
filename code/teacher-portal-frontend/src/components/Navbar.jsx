import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/scenarios", label: "Scenarios" },
  { to: "/scenarios/create", label: "Create" },
  { to: "/sessions/start", label: "Start Session" },
  { to: "/students", label: "Students" },
  { to: "/guidelines/upload", label: "Guidelines" },
];

export default function Navbar() {
  return (
    <header className="navbar">
      <div className="navbar-brand">
        <div className="navbar-brand-icon" aria-hidden="true">🩺</div>
        <div className="navbar-brand-text">
          <strong>Teacher Portal</strong>
          <span>VR Nursing Wound Care Simulation</span>
        </div>
      </div>

      <nav className="navbar-links" aria-label="Main navigation">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            end={item.end}
            to={item.to}
            className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
