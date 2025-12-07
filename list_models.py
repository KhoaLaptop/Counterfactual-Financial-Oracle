import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv("counterfactual_oracle/.env")
api_key = os.getenv("OPENAI_API_KEY") # We stored the Gemini key here

genai.configure(api_key=api_key)

print("Available Models:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
