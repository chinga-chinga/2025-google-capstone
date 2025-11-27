import os
from dotenv import load_dotenv
from google import genai

# Load the key from .env
load_dotenv()

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("❌ Error: GOOGLE_API_KEY not found in .env")
    exit(1)

print(f"🔍 Checking available models for your API Key...")

try:
    client = genai.Client(api_key=api_key)
    
    # List all models
    print("\n✅ Available Gemini Models:")
    found_any = False
    
    # Simple iteration without complex filters
    for m in client.models.list():
        # Check if 'gemini' is in the name (case insensitive)
        if "gemini" in m.name.lower():
            # Try to get display name, fallback to empty string if missing
            d_name = getattr(m, 'display_name', '')
            print(f"  • {m.name} {f'({d_name})' if d_name else ''}")
            found_any = True
    
    if not found_any:
        print("  (No models containing 'gemini' found. Check your API key.)")

except Exception as e:
    print(f"\n❌ Error fetching models: {e}")