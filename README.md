# 🩹 FYP WoundCareSim

A **virtual wound-care training simulator** for nursing education.

This project helps nursing students practice communication, clinical reasoning, and dressing workflow in a safe environment using AI-driven patient/staff interactions, guided scenario steps, and automated feedback.

---

## 1) What this project is about

**FYP WoundCareSim** is designed to simulate bedside wound-care sessions where a student:

1. Takes focused patient history.
2. Performs assessment and decision-making.
3. Selects and verifies cleaning/dressing materials.
4. Receives feedback and scoring after each stage.

The main goal is to make practice **repeatable, measurable, and reflective** before real clinical exposure.

---

## 2) Educational goals

- Improve student confidence in wound-care procedures.
- Reinforce structured communication with patients.
- Support step-by-step clinical workflow adherence.
- Provide instant, explainable feedback for learning.
- Enable scenario-based assessment with consistent criteria.

---

## 3) Core capabilities

- **Scenario-based simulation** with session tracking.
- **Multi-agent responses** (patient, communication, knowledge, clinical, staff nurse).
- **Step/state progression** through a defined workflow.
- **RAG-enhanced support** using knowledge retrieval.
- **Audio support** (speech-to-text + text-to-speech).
- **Evaluation pipeline** for performance feedback.

---

## 4) High-level system view

### Main backend (`Backend_WoundCareSim`)
Handles the production-style simulation workflow:
- API routes for sessions, scenarios, and audio.
- Agent coordination and state transitions.
- Evaluation, scoring, and event tracking.

### Prototype app (`kushan`)
A lightweight UI-driven variant used for earlier experimentation and rapid testing.

---

## 5) Learning flow in the simulator

A typical session follows:

1. **Start session** with scenario and student ID.
2. **History-taking** conversation with virtual patient.
3. **Guided progression** to next clinical step.
4. **Material verification/actions** during cleaning & dressing.
5. **Evaluation output** with feedback narrative.

---
