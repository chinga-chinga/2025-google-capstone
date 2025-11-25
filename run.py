import asyncio
import os
import sys
import time
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import vpc_broker_app 

# --- RATE LIMITING HELPER (AGGRESSIVE) ---
async def rate_limited_run(runner, **kwargs):
    print("   [Rate Limiter] Stepping through events...")
    async for event in runner.run_async(**kwargs):
        yield event
        # 10 second delay ensures < 6 requests per minute
        # This is slow but safe for the Free Tier.
        print("   [Rate Limiter] Waiting 10s...")
        await asyncio.sleep(10)

async def run_test_with_approval_loop(runner: Runner, user_query: str):
    print(f"\n--- 🚀 RUNNING TEST: {user_query} ---")
    
    session_id = f"test-session-{hash(user_query)}"
    await runner.session_service.create_session(
        app_name=vpc_broker_app.name, user_id="test_user", session_id=session_id
    )
    
    # --- FUNCTION DEFINITION ---
    def find_pause_request(events):
        print("   [System] Scanning events for pause signal...")
        for event in events:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if (
                        part.function_call and 
                        part.function_call.name == "adk_request_confirmation"
                    ):
                        print("      ✅ FOUND 'adk_request_confirmation'!")
                        
                        args = part.function_call.args
                        hint = None
                        # 1. Check nested payload (ADK standard)
                        if 'toolConfirmation' in args:
                            hint = args['toolConfirmation'].get('hint')
                        # 2. Fallback check
                        if not hint:
                            hint = args.get('hint')
                        # 3. Payload fallback
                        if not hint and 'payload' in args:
                             hint = args['payload'].get('hint')
                            
                        return part.function_call.id, event.invocation_id, hint
        return None, None, None

    # --- STEP 1: Send Query ---
    print("...Broker receiving request...")
    query_content = types.Content(role="user", parts=[types.Part(text=user_query)])
    events = []
    
    async for event in rate_limited_run(
        runner,
        user_id="test_user",
        session_id=session_id,
        new_message=query_content,
    ):
        events.append(event)

    # Find final text
    final_text = "..."
    for event in reversed(events):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    final_text = part.text
                    break
        if final_text != "...": break
    print(f"\nVPCAccessBroker > {final_text}")

    # --- STEP 2: Check for Pause ---
    # THIS LINE WAS THE ERROR. It calls the function defined above.
    approval_id, invocation_id, hint_text = find_pause_request(events)

    if approval_id:
        print(f"\n⏸️  SYSTEM PAUSED: High Risk Detected.")
        print(f"   Alert: {hint_text}") 

        print("\n...Simulating Security Engineer: 'APPROVED'...")
        print("   [Rate Limiter] Pause for approval (5s)...")
        await asyncio.sleep(5) 
        
        approval_response = types.Content(
            role="user",
            parts=[types.Part(function_response=types.FunctionResponse(
                id=approval_id,
                name="adk_request_confirmation",
                response={"confirmed": True} 
            ))]
        )

        # --- STEP 3: Resume ---
        print("...Resuming Workflow...")
        resume_events = [] 
        
        async for event in rate_limited_run(
            runner,
            user_id="test_user",
            session_id=session_id,
            new_message=approval_response, 
            invocation_id=invocation_id 
        ):
            resume_events.append(event)
            
        final_response = "No final response."
        for event in reversed(resume_events):
            if event.content and event.content.parts:
                 for part in event.content.parts:
                    if part.text:
                        final_response = part.text
                        break
        print(f"\nVPCAccessBroker (Final) > {final_response}")
    
    else:
        print("\n✅ System finished without requesting approval (Auto-Approved).")

    print("--- ✅ TEST COMPLETE ---")


async def main():
    load_dotenv() 

    if "GOOGLE_API_KEY" not in os.environ:
        print("❌ ERROR: GOOGLE_API_KEY not found.")
        sys.exit(1)

    session_service = InMemorySessionService()
    runner = Runner(app=vpc_broker_app, session_service=session_service)

    # Test 1: Happy Path
    await run_test_with_approval_loop(
        runner,
        "I need to connect my checkout-service to the billing-db on port 5432."
    )

    print("\n⏳ Waiting 30 seconds to reset rate limits completely...")
    await asyncio.sleep(30)

    # Test 2: High Risk Path
    await run_test_with_approval_loop(
        runner,
        "Can you open port 5432 from the public-internet to the admin-db?"
    )

if __name__ == "__main__":
    asyncio.run(main())