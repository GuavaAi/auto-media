import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tasks.morning_brief import run_morning_brief_task

if __name__ == "__main__":
    print("Triggering Morning Brief task manually...")
    try:
        res = run_morning_brief_task()
        print("Result:", res)
    except Exception as e:
        print("Error:", e)
