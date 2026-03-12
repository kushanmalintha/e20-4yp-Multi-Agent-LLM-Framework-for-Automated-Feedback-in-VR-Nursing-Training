import axios from "axios";

const API = axios.create({
  baseURL: "http://localhost:8000",
});

export async function getScenarios() {
  const response = await API.get("/teacher/scenario/list");
  return response.data;
}

export async function getScenarioById(scenarioId) {
  const response = await API.get(`/teacher/scenario/${scenarioId}`);
  return response.data;
}

export async function createScenario(data) {
  const response = await API.post("/teacher/scenario/create", data);
  return response.data;
}

export async function updateScenario(data) {
  const response = await API.post("/teacher/scenario/update", data);
  return response.data;
}

export async function startSession(data) {
  const response = await API.post("/session/start", data);
  return response.data;
}

export async function uploadGuideline(file) {
  const form = new FormData();
  form.append("file", file);
  const response = await API.post("/teacher/vector/upload", form);
  return response.data;
}

export async function getStudentSessions(studentId) {
  const response = await API.get(`/students/${studentId}/sessions`);
  return response.data;
}

export async function getSessionDetail(studentId, sessionId) {
  const response = await API.get(`/students/${studentId}/sessions/${sessionId}`);
  return response.data;
}
