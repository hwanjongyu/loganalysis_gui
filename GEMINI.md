# 🛸 GEMINI.md: Antigravity Agent Protocol

This document defines the architectural guardrails and **Hybrid Model Routing** strategy for the Antigravity AI Agent. Adherence is mandatory to ensure cross-model synergy and production-grade development.

---

## 🤖 Model Routing & Phase Ownership

The Agent transitions between models dynamically based on the active development phase:

| Phase | Model | Assigned Role | Primary Responsibilities |
| --- | --- | --- | --- |
| **1. Orchestration** | `Gemini 3 Pro` | **Project Manager** | Context mapping (1M+ tokens), `implementation_plan.md`, & dependency analysis. |
| **2. Core Build** | `Claude Sonnet 4.5` | **Lead Developer** | Production Python/PyQt5, threaded workers, and complex business logic. |
| **3. Validation** | `Claude Opus 4.5` | **Senior Tech Lead** | High-level reasoning, concurrency audits, and security validation. |
| **4. QA & Routine** | `Gemini 3 Flash` | **QA Engineer** | Unit/UI tests, documentation, Terminal commands, and Git management. |
| **5. Verification** | `GPS-OSS 120B` | **Reviewer** | Fast localized logic checks and independent code verification. |

---

## 📊 Post-Task Transparency (Mandatory)

Every task must conclude with a standardized **Model & Skill Usage Report**:

> ### [Model & Skill Usage Report]
> 
> 
> * **Persona:** [e.g., Lead Developer]
> * **Active Model:** [e.g., Claude Sonnet 4.5 (Thinking)]
> * **Skills Executed:**
> * `skill_name`: [e.g., `edit_file` on `loganalysis_gui.py`]
> * `skill_name`: [e.g., `run_terminal_command` for linting]
> 
> 
> * **Outcome:** [Success/Fail summary]
> 
> 

---

## 🔄 The Hybrid Workflow Loop

1. **Analyze (G3 Pro):** Perform deep-read of codebase to establish the "source of truth."
2. **Design (C4.5 Opus):** Review and harden the implementation plan.
3. **Build (C4.5 Sonnet):** Execute the code changes with "Thinking" mode enabled.
4. **Verify (G3 Flash):** Run builds, execute tests, and update documentation.

---

## 🛠 Execution Guardrails

* **No Unsolicited Build:** Do not begin implementation until the user explicitly approves the `implementation_plan.md`.
* **High-Impact Alerts:** Real-time notification is required for file deletions or script executions *prior* to the final report.
* **Fail-Forward Reporting:** If a command fails, report the error logs immediately along with which model is being engaged to troubleshoot.
