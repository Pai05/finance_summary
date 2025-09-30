import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from your .env file
load_dotenv()

def list_available_models():
    """
    Connects to the Google AI service and lists all available Gemini models
    that support the 'generateContent' method required for this project.
    """
    try:
        # 1. Configure the API key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("--> ERROR: GEMINI_API_KEY not found in your .env file.")
            print("    Please ensure the file is present and the key is correct.")
            return

        genai.configure(api_key=api_key)
        print("Successfully configured API key.")
        print("-" * 30)

        # 2. List all available models and filter them
        print("Fetching available models for your API key...")
        
        available_models = []
        for m in genai.list_models():
            # The 'generateContent' method is what we use for summarization.
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        # 3. Print the results
        if available_models:
            print("\n✅ SUCCESS! Found models you can use:")
            for model_name in available_models:
                print(f"   - {model_name}")
            print("\n--> ACTION: Copy one of the model names from the list above")
            print("    (e.g., 'models/gemini-1.5-pro-latest') and paste it into your")
            print("    ai_processor.py file.")
        else:
            print("\n--> ERROR: No compatible models were found for your account.")
            print("    This confirms the permission issue with your Google Cloud Project.")
            print("    Please double-check that the 'Vertex AI API' is enabled and")
            print("    that a billing account is linked to the correct project.")

    except Exception as e:
        print(f"\n--> CRITICAL ERROR: An exception occurred while trying to connect.")
        print(f"    Error details: {e}")
        print("\n    This almost always means there is a problem with your Google Cloud")
        print("    Project's configuration (API not enabled or billing not linked).")

if __name__ == "__main__":
    list_available_models()

