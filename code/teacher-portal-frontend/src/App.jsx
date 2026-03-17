import { Navigate, Route, Routes } from "react-router-dom";

import Navbar from "./components/Navbar.jsx";
import CreateScenario from "./pages/CreateScenario.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import EditScenario from "./pages/EditScenario.jsx";
import ScenarioList from "./pages/ScenarioList.jsx";
import ScenarioDetails from "./pages/ScenarioDetails.jsx";
import SessionDetail from "./pages/SessionDetail.jsx";
import StartSession from "./pages/StartSession.jsx";
import StudentPerformance from "./pages/StudentPerformance.jsx";
import UploadGuidelines from "./pages/UploadGuidelines.jsx";

export default function App() {
  return (
    <div className="app-shell">
      <Navbar />
      <main className="page-shell">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/scenarios" element={<ScenarioList />} />
          <Route path="/scenarios/create" element={<CreateScenario />} />
          <Route path="/scenarios/:scenarioId" element={<ScenarioDetails />} />
          <Route path="/scenarios/:scenarioId/edit" element={<EditScenario />} />
          <Route path="/sessions/start" element={<StartSession />} />
          <Route path="/students" element={<StudentPerformance />} />
          <Route path="/students/:studentId/sessions/:sessionId" element={<SessionDetail />} />
          <Route path="/guidelines/upload" element={<UploadGuidelines />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
