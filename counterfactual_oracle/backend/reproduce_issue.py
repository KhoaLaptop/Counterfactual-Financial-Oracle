import os
from app.domain.agents.critic import CriticAgent
from app.domain.agents.debate_agent import DebateAgent

# Mock API keys
os.environ["GEMINI_API_KEY"] = "fake_key"
os.environ["DEEPSEEK_API_KEY"] = "fake_key"

try:
    print("Initializing CriticAgent...")
    critic = CriticAgent(api_key="fake_key")
    print("CriticAgent initialized.")

    print("Initializing DebateAgent...")
    debate = DebateAgent(gemini_api_key="fake_key", deepseek_api_key="fake_key")
    print("DebateAgent initialized.")

except Exception as e:
    print(f"Caught exception: {e}")
    import traceback
    traceback.print_exc()
