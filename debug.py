import os
import sys
from dotenv import load_dotenv

print("--- 🚀 Starting Debugger ---")

# 1. Check for .env file
print("\n[Check 1: .env File]")
env_path = ".env"
if os.path.exists(env_path):
    print("  ✅ .env file FOUND.")
    # 2. Try to load it
    try:
        load_dotenv()
        print("  ✅ dotenv loaded successfully.")
    except Exception as e:
        print(f"  ❌ FAILED to load dotenv: {e}")
        sys.exit(1)
else:
    print("  ❌ CRITICAL FAILURE: .env file NOT FOUND.")
    print("     Make sure your file is named exactly '.env' (not '.env.txt')")
    sys.exit(1)

# 3. Check for API Key
print("\n[Check 2: GOOGLE_API_KEY]")
api_key = os.environ.get("GOOGLE_API_KEY")

if api_key:
    # Do not print the full key, just the first few chars
    print(f"  ✅ GOOGLE_API_KEY FOUND. Starts with: '{api_key[:4]}...'")
else:
    print("  ❌ CRITICAL FAILURE: GOOGLE_API_KEY is NOT SET in the environment.")
    print("     Check your .env file. Is the variable name *exactly* 'GOOGLE_API_KEY'?")
    sys.exit(1)

# 4. Check for project files
print("\n[Check 3: Project Files]")
files_to_check = ["agent.py", "run.py", "review_list.json"]
all_files_found = True
for f in files_to_check:
    if os.path.exists(f):
        print(f"  ✅ {f} FOUND.")
    else:
        print(f"  ❌ FAILED: {f} NOT FOUND.")
        all_files_found = False

if all_files_found:
    print("\n--- ✅ Debugger Complete: Environment looks OK ---")
    print("If this script passes, your problem is likely a network issue")
    print("or an *invalid* API key (e.g., Gemini API not enabled).")
else:
    print("\n--- ❌ Debugger Failed: Please fix the file errors above. ---")