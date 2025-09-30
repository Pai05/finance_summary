import os
import google.generativeai as genai
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Configure the API key once when the module is loaded
try:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
except ValueError as e:
    print(f"CRITICAL ERROR on startup: {e}")

# --- Core Functions ---

def _call_gemini_with_retry(model, prompt, max_retries=3):
    """
    Internal function to call the Gemini API with a prompt.
    Includes a retry mechanism for transient server errors.
    """
    retries = 0
    while retries < max_retries:
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            if "503" in str(e) or "unavailable" in str(e).lower():
                retries += 1
                wait_time = 2 ** retries
                print(f"Warning: Gemini API returned a server error. Retrying in {wait_time}s ({retries}/{max_retries})...")
                time.sleep(wait_time)
            else:
                raise e
    raise Exception(f"Failed to get a valid response from Gemini after {max_retries} retries.")

def select_top_articles(articles, ticker):
    """Uses Gemini to select the top 5-7 articles from a list."""
    print(f"Selecting top articles for {ticker}...")
    
    # **FIX: Using a model name confirmed to be available for your account.**
    model = genai.GenerativeModel('models/gemini-pro-latest')
    
    headlines = [f"{idx+1}. {article['title']}" for idx, article in enumerate(articles)]
    prompt = (
        "You are a financial news analyst. From the following list of headlines, "
        "select the top 5 to 7 most significant articles for an investor "
        f"researching the stock {ticker}. Prioritize specific financial data or major company announcements. "
        "Return your answer as a comma-separated list of numbers corresponding to the headlines "
        "(e.g., '1, 3, 5, 8, 12').\n\n"
        "Headlines:\n" + "\n".join(headlines)
    )
    
    try:
        selected_indices_str = _call_gemini_with_retry(model, prompt)
        selected_indices = [int(i.strip()) - 1 for i in selected_indices_str.split(',') if i.strip().isdigit()]
        return [articles[i] for i in selected_indices if 0 <= i < len(articles)]

    except Exception as e:
        print(f"CRITICAL ERROR selecting articles with Gemini: {e}")
        return articles[:5] # Fallback

def generate_summary_with_ai(articles, ticker, history):
    """Uses Gemini to generate a summary from the full text of selected articles."""
    print(f"Generating summary for {ticker}...")
    
    # **FIX: Using a model name confirmed to be available for your account.**
    model = genai.GenerativeModel('models/gemini-pro-latest')

    full_text = "\n\n---\n\n".join(
        f"Article Title: {article['title']}\n\n{article.get('text', 'Content not available.')}" 
        for article in articles
    )
    
    history_context = f"For context, here is the summary from the previous day:\n{history}\n\n" if history else ""

    prompt = (
        f"You are an expert financial analyst. Your task is to provide a concise, insightful summary "
        f"of the latest news for the stock {ticker}. The summary must be under 500 words.\n\n"
        f"Based on the following articles, generate a summary that includes a section titled 'What changed today'.\n\n"
        f"{history_context}"
        f"Here is the full text of today's most important articles:\n{full_text}"
    )
    
    try:
        summary = _call_gemini_with_retry(model, prompt)
        return summary
    except Exception as e:
        print(f"CRITICAL ERROR generating summary with Gemini: {e}")
        return "An error occurred while generating the summary. See console for details."

