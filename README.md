# VPC Firewall Concierge Agent 🛡️

**Track:** Enterprise Agents

## 🚨 The Problem

In cloud environments, developers need to connect services (e.g., GKE to Cloud SQL), but they don't understand VPC firewall rules. They file tickets, creating a bottleneck for Network Engineers who must manually validate and apply changes. This slows down velocity and invites human error.

## 💡 The Solution

The **VPC Firewall Concierge** is an autonomous agentic workflow that allows developers to request connectivity in plain English. It features a **Governance Guardrail**:

1.  **Auto-Approval:** Low-risk requests (e.g., internal app-to-db) are validated and applied instantly.
2.  **Conditional LRO:** High-risk requests (e.g., public ingress, admin ports) trigger a **Long-Running Operation**. The agent PAUSES execution and requests human approval from a Security Engineer before resuming.

## 🏗️ Architecture

The system utilizes the **Google ADK** and a multi-agent architecture:

- **`ConciergeAgent` (Orchestrator):** Manages the user intent and conversation state.
- **`PolicyAgent` (The Guardrail):**
  - **Tool:** `check_policy_and_gate`
  - **Logic:** Checks request against a `review_list.json`.
  - **Pattern:** Implements a **Conditional Pause**. If a match is found, it raises an `adk_request_confirmation` event.
- **`VpcFirewallAgent` (The Actuator):** Executes the `gcloud` commands (simulated for safety) only after policy clearance.

## 🛠️ Tech Stack

- **Framework:** Google Agent Development Kit (ADK)
- **Model:** Gemini 2.5 Flash Lite
- **Pattern:** Human-in-the-Loop (HITL) / Long-Running Operations (LRO)
- **Environment:** Python, UV

## 🚀 How to Run

1.  Clone the repo.
2.  Install dependencies: `uv pip install google-adk python-dotenv`
3.  Add your API Key to `.env`: `GOOGLE_API_KEY=...`
4.  Run the test harness: `uv run run.py`

## 🧪 Verification

The `run.py` script executes two test cases:

1.  **Happy Path:** A safe request that is auto-approved.
2.  **High-Risk Path:** A dangerous request that triggers the Pause/Resume workflow, simulating a human intervention.
