import asyncio
import os
import sys
import time
import logging
import warnings
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# --- 🔇 SILENCE THE NOISE ---
warnings.filterwarnings("ignore")
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("google_genai").setLevel(logging.ERROR)
logging.getLogger("google_adk").setLevel(logging.ERROR)
logging.getLogger("google.adk").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.basicConfig(level=logging.INFO, format='%(message)s')
# -------------------------

from agent import vpc_broker_app 

# --- VISUAL HELPERS ---
def print_header(title):
    print("\n" + "="*80)
    print(f"🎬  DEMO SCENARIO: {title}")
    print("="*80 + "\n")

def print_step(message):
    print(f"\n🔸 [STEP] {message}")

def print_agent_msg(agent, text):
    print(f"\n🤖 {agent} > \033[1m{text}\033[0m") 

# --- RATE LIMITING HELPER ---
async def rate_limited_run(runner, **kwargs):
    print("   ⏳ [System] Processing...", end="", flush=True)
    async for event in runner.run_async(**kwargs):
        yield event
        print(".", end="", flush=True) 
        await asyncio.sleep(5) 
    print() 

async def run_test_with_approval_loop(runner: Runner, user_query, scenario_name):
    print_header(scenario_name)
    
    session_id = f"test-session-{hash(user_query)}"
    await runner.session_service.create_session(
        app_name=vpc_broker_app.name, user_id="test_user", session_id=session_id
    )
    
    def find_pause_request(events):
        for event in events:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if (part.function_call and part.function_call.name == "adk_request_confirmation"):
                        
                        args = part.function_call.args
                        hint = args.get('hint')
                        if not hint and 'payload' in args: hint = args['payload'].get('hint')
                        if not hint and 'toolConfirmation' in args: hint = args['toolConfirmation'].get('hint')
                        return part.function_call.id, event.invocation_id, hint or "Review Required"
        return None, None, None

    # --- STEP 1: INITIAL REQUEST ---
    print(f"👤 USER: '{user_query}'\n")
    
    query_content = types.Content(role="user", parts=[types.Part(text=user_query)])
    events = []
    
    async for event in rate_limited_run(runner, user_id="test_user", session_id=session_id, new_message=query_content):
        events.append(event)

    # --- STEP 2: CHECK FOR PAUSE (LRO) ---
    approval_id, invocation_id, hint_text = find_pause_request(events)

    if approval_id:
        print("\n" + "!"*80)
        print(f"⏸️  SYSTEM ALERT: High Risk Operation Detected via Policy Agent")
        print(f"   Locking Workflow. Reason: {hint_text}") 
        print("!"*80)

        print("\n👮 SECURITY ENGINEER: Reviewing request...")
        time.sleep(2)
        print("   Action: APPROVED [✔]")
        
        approval_response = types.Content(
            role="user",
            parts=[types.Part(function_response=types.FunctionResponse(
                id=approval_id,
                name="adk_request_confirmation",
                response={"confirmed": True} 
            ))]
        )

        print("\n▶️  RESUMING WORKFLOW...\n")
        resume_events = [] 
        async for event in rate_limited_run(runner, user_id="test_user", session_id=session_id, new_message=approval_response, invocation_id=invocation_id):
            resume_events.append(event)
            
        final_response = "Rule applied."
        for event in reversed(resume_events):
            if event.content and event.content.parts:
                 for part in event.content.parts:
                    if part.text:
                        final_response = part.text
                        break
        print_agent_msg("VPCAccessBroker", final_response)
    
    else:
        # Find final text for happy path
        final_text = "No final response."
        for event in reversed(events):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_text = part.text
                        break
            if final_text != "No final response.": break
        
        print_agent_msg("VPCAccessBroker", final_text)

        # --- SMART STATUS CHECK ---
        # If the agent didn't throw a mechanical pause, did it at least verbalize one?
        lower_text = final_text.lower()
        if "pending" in lower_text or "review" in lower_text or "paused" in lower_text:
             print("\n🛑 GOVERNANCE CHECK: High Risk Detected. Request Paused/Blocked by Agent.")
        else:
             print("\n✅ GOVERNANCE CHECK: Passed. Auto-Approved.")

    print("\n🏁 END SCENARIO\n")


async def main():
    load_dotenv() 
    if "GOOGLE_API_KEY" not in os.environ:
        print("❌ ERROR: GOOGLE_API_KEY not found.")
        sys.exit(1)

    print("\n🚀 SYSTEM ONLINE: VPC Access Broker [Mode: VERBOSE/TRACE]")
    session_service = InMemorySessionService()
    runner = Runner(app=vpc_broker_app, session_service=session_service)
    
    print("\n⚠️  Initial Cooldown (30s) to clear any previous rate limits...")
    await asyncio.sleep(30)

    # 2. Run Test 1
    await run_test_with_approval_loop(
        runner,
        user_query="I need to connect my checkout-service to the billing-db on port 5432.",
        scenario_name="HAPPY PATH (Internal Service Connection)"
    )

    # 3. Rate Limit Cool-down
    print("⏳ System Cooldown (15s) before Test 2...")
    await asyncio.sleep(15)

    # 4. Run Test 2
    await run_test_with_approval_loop(
        runner,
        user_query="Can you open port 5432 from the public-internet to the admin-db?",
        scenario_name="HIGH-RISK PATH (Public Ingress)"
    )

if __name__ == "__main__":
    asyncio.run(main())





    