import json
import logging
from google.adk.agents import LlmAgent
from google.adk.apps.app import App, ResumabilityConfig
from google.adk.models.google_llm import Gemini
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.agent_tool import AgentTool

# Set up logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("google.adk").setLevel(logging.ERROR)

POLICY_FILE = "review_list.json"
REGISTRY_FILE = "service_registry.json"

# --- 1. THE GCP QUERY AGENT (The Eyes) ---
def lookup_resource_tag(friendly_name: str) -> str:
    """
    Translates a friendly name (e.g., 'checkout-service') into a network tag (e.g., 'app:checkout').
    Returns 'UNKNOWN' if not found.
    """
    logging.info(f"[GcpQueryTool] Looking up: {friendly_name}")
    try:
        with open(REGISTRY_FILE, 'r') as f:
            registry = json.load(f)
        
        # Simple fuzzy match
        for key, data in registry.items():
            if friendly_name.lower() in key.lower():
                return data['tag']
        return "UNKNOWN"
    except FileNotFoundError:
        return "ERROR: Registry file not found."

gcp_query_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash"),
    name="GcpQueryAgent",
    instruction="""
    You are the Cloud Infrastructure Map. 
    1. Use 'lookup_resource_tag' to translate the name.
    2. CRITICAL: You MUST output the result in text.
       Example: "The tag for checkout-service is app:checkout."
    """,
    tools=[lookup_resource_tag]
)

# --- 2. THE POLICY AGENT (The Guardrail) ---
def _check_match(rule_val: str | int, request_val: str | int) -> bool:
    if rule_val is None or rule_val == '*':
        return True
    return rule_val == request_val

def check_policy_and_gate(
    source_tag: str, 
    dest_tag: str, 
    port: int, 
    tool_context: ToolContext
) -> dict:
    logging.info(f"[PolicyTool] Checking: {source_tag} -> {dest_tag}:{port}")
    with open(POLICY_FILE, 'r') as f:
        review_list = json.load(f)

    match_reason = None
    for rule in review_list:
        from_match = _check_match(rule.get('from'), source_tag)
        to_match = _check_match(rule.get('to'), dest_tag)
        port_match = _check_match(rule.get('port'), port)
        if from_match and to_match and port_match:
            match_reason = rule['reason']
            break

    if match_reason:
        logging.warning(f"[PolicyTool] HIGH-RISK: {match_reason}")
        if tool_context.tool_confirmation and tool_context.tool_confirmation.confirmed:
            logging.info("[PolicyTool] LRO Resuming: Human Approved.")
            return {"status": "approved", "approver": "human", "reason": match_reason}
        else:
            logging.info("[PolicyTool] LRO Pausing...")
            hint = f"HIGH-RISK: {source_tag}->{dest_tag}:{port}. Reason: {match_reason}"
            tool_context.request_confirmation(hint=hint, payload={"hint": hint})
            return {"status": "pending_review"}
    else:
        logging.info("[PolicyTool] LOW-RISK. Auto-approving.")
        return {"status": "approved", "approver": "policy_engine"}

policy_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash"),
    name="PolicyAgent",
    instruction="""
    You are the Policy Guardrail.
    1. Use 'check_policy_and_gate' to validate the request.
    2. CRITICAL: You MUST summarize the tool output in text.
       Example: "Status: approved. Reason: Low risk."
    """,
    tools=[check_policy_and_gate]
)

# --- 3. THE FIREWALL AGENT (The Actuator) ---
def apply_firewall_rule(source: str, dest: str, port: int) -> str:
    """Applies the actual firewall rule to the network infrastructure."""
    logging.info(f"[FirewallTool] APPLYING RULE: {source} -> {dest}:{port}")
    return f"SUCCESS: Rule created for {source} to {dest} on port {port}."

firewall_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash"),
    name="FirewallAgent",
    instruction="""
    You are the Firewall Operator. 
    1. Use 'apply_firewall_rule'.
    2. CRITICAL: Output the tool result in text.
       Example: "Rule created successfully."
    """,
    tools=[apply_firewall_rule]
)

# --- 4. THE VPC ACCESS BROKER (The Boss) ---
vpc_broker_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash"),
    name="VPCAccessBrokerAgent",
    instruction="""
    You are the VPC Access Broker. You act as an intelligent interface between developers and infrastructure.

    To fulfill a request, you MUST strictly follow this sequence. Do not skip steps.

    **STEP 1: RESOLVE TAGS (MANDATORY)**
    You need two tags: SOURCE and DESTINATION.
    - Call 'GcpQueryAgent' to get the tag for the SOURCE name.
    - Call 'GcpQueryAgent' to get the tag for the DESTINATION name.
    - CRITICAL: Do NOT guess tags. If you don't know a tag, ask 'GcpQueryAgent'. Even for 'public-internet', you MUST ask the agent.

    **STEP 2: CHECK POLICY**
    - Once you have the Source Tag (e.g. 'app:checkout'), Destination Tag (e.g. 'db:billing'), and Port, call 'PolicyAgent'.
    - Pass these exact values.

    **STEP 3: EXECUTE (Conditional)**
    - IF 'PolicyAgent' returns "approved": Call 'FirewallAgent' to apply the rule.
    - IF 'PolicyAgent' returns "pending_review": Inform the user the request is paused for approval.

    **STEP 4: FINAL REPORT (CRITICAL)**
    - After the Firewall Agent finishes (or if Policy pauses), you MUST summarize the final outcome to the user in a clear sentence.
    - Example: "Success: Firewall rule applied connecting app:checkout to db:billing."

    User Request format: "Connect [source name] to [dest name] on [port]"
    """,
    tools=[
        AgentTool(gcp_query_agent),
        AgentTool(policy_agent), 
        AgentTool(firewall_agent)
    ]
)

# --- 5. THE APP ---
vpc_broker_app = App(
    name="vpc_broker_app",
    root_agent=vpc_broker_agent,
    resumability_config=ResumabilityConfig(is_resumable=True)
)