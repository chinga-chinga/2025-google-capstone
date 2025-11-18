import json
import logging
from google.adk.agents import LlmAgent
from google.adk.apps.app import App, ResumabilityConfig
from google.adk.models.google_llm import Gemini
from google.adk.tools.tool_context import ToolContext

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("google.adk").setLevel(logging.ERROR)

POLICY_FILE = "review_list.json"

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
    logging.info(f"[Tool] Checking policy: {source_tag} -> {dest_tag}:{port}")

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
        logging.warning(f"[Tool] HIGH-RISK: Match found. Reason: {match_reason}")
        if tool_context.tool_confirmation and tool_context.tool_confirmation.confirmed:
            logging.info("[Tool] LRO Resuming: Human has approved.")
            return {
                "status": "approved_by_human",
                "review_needed": True,
                "reason": match_reason
            }
        else:
            logging.info("[Tool] LRO Pausing: Requesting human confirmation...")
            
            hint_text = f"Request: {source_tag} -> {dest_tag}:{port}. Reason: {match_reason}"
            
            # We pass the hint in multiple ways to be safe
            tool_context.request_confirmation(
                hint=hint_text,
                payload={"hint": hint_text}
            )
            return {
                "status": "pending_human_review",
                "review_needed": True
            }
    else:
        logging.info("[Tool] LOW-RISK: No match found. Auto-approving.")
        return {
            "status": "auto-approved",
            "review_needed": False
        }

# Define the agent with STRONGER instructions
policy_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash-lite"),
    name="PolicyAgent",
    instruction="""
    You are a security policy agent. 
    
    1. Call the check_policy_and_gate tool.
    2. The tool will return a JSON object.
    3. YOU MUST READ THAT JSON AND SUMMARIZE IT IN TEXT.
    
    DO NOT STOP after calling the tool.
    DO NOT return an empty response.
    ALWAYS output a sentence like: "Status: [status]. Review needed: [true/false]."
    """
    ,
    tools=[check_policy_and_gate]
)

policy_app = App(
    name="policy_app",
    root_agent=policy_agent,
    resumability_config=ResumabilityConfig(is_resumable=True) 
)