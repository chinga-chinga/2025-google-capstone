import asyncio
import os
import sys
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import policy_app

async def run_test_with_approval_loop(runner: Runner, user_query: str):
    print(f"\n--- 🚀 RUNNING TEST: {user_query} ---")
    
    session_id = f"test-session-{hash(user_query)}"
    await runner.session_service.create_session(
        app_name=policy_app.name, user_id="test_user", session_id=session_id
    )
    
    def did_agent_pause(events):
        for event in events:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if (
                        part.function_call and 
                        part.function_call.name == "adk_request_confirmation"
                    ):
                        print("\n⏸️  AGENT PAUSED: Waiting for human approval.")
                        
                        args = part.function_call.args
                        hint = None

                        # --- 1. NEW LOGIC: Check for nested toolConfirmation ---
                        if 'toolConfirmation' in args:
                            hint = args['toolConfirmation'].get('hint')
                        
                        # Fallback: Check top level
                        if not hint:
                            hint = args.get('hint')
                            
                        return part.function_call.id, event.invocation_id, hint
        return None, None, None

    # --- STEP 1: Send the initial query ---
    print("...Sending initial user query...")
    # Force the model to speak by appending instructions
    forced_query = user_query + " Respond with a text summary of the result."
    
    query_content = types.Content(role="user", parts=[types.Part(text=forced_query)])
    events = []
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session_id,
        new_message=query_content,
    ):
        events.append(event)
        
    final_text_response = "No final response." 
    for event in reversed(events):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    final_text_response = part.text
                    break 
        if final_text_response != "No final response.":
            break
            
    print(f"\nPolicyAgent > {final_text_response}")

    # --- STEP 2: Check if the agent paused ---
    approval_id, invocation_id, hint_text = did_agent_pause(events)

    if approval_id:
        print(f"   Reason: {hint_text}") 

        print("\n...Simulating human: 'APPROVE'...")
        await asyncio.sleep(1) 
        
        approval_response = types.Content(
            role="user",
            parts=[types.Part(function_response=types.FunctionResponse(
                id=approval_id,
                name="adk_request_confirmation",
                response={"confirmed": True} 
            ))]
        )

        print("...Resuming agent execution...")
        resume_events = [] 
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session_id,
            new_message=approval_response, 
            invocation_id=invocation_id 
        ):
            resume_events.append(event)
            
        resume_response = "No final response post-approval."
        for event in reversed(resume_events):
            if event.content and event.content.parts:
                 for part in event.content.parts:
                    if part.text:
                        resume_response = part.text
                        break
            if resume_response != "No final response post-approval.":
                break
                
        print(f"\nPolicyAgent (Post-Approval) > {resume_response}")

    print("--- ✅ TEST COMPLETE ---")


async def main():
    load_dotenv() 

    if "GOOGLE_API_KEY" not in os.environ:
        print("❌ ERROR: GOOGLE_API_KEY not found.")
        sys.exit(1)

    session_service = InMemorySessionService()
    runner = Runner(app= policy_app, session_service=session_service)

    await run_test_with_approval_loop(
        runner,
        "Validate request: source 'app:checkout' to 'db:billing' on port 5432."
    )

    await run_test_with_approval_loop(
        runner,
        "Validate request: source 'app:public-ingress' to 'db:admin' on port 5432."
    )

if __name__ == "__main__":
    asyncio.run(main())