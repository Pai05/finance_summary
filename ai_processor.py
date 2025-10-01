import os
import time
import google.generativeai as genai
from google.api_core import exceptions

def _configure_genai():
    """Configures the Gemini AI with the API key."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL ERROR on startup: GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)

def _call_gemini_with_retry(model, prompt):
    """Calls the Gemini API with an exponential backoff retry mechanism."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except exceptions.ResourceExhausted as e:
            print(f"Warning: Quota exhausted. {e}")
            break 
        except Exception as e:
            # Check for temporary server-side errors
            if isinstance(e, (exceptions.ServiceUnavailable, exceptions.DeadlineExceeded)):
                wait_time = (2 ** attempt)
                print(f"Warning: Gemini API call failed with a temporary error: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                # For all other errors (like 404, 400), don't retry.
                print(f"CRITICAL ERROR calling Gemini: {e}")
                break # Exit the loop on non-retryable errors
    return None # Return None if all retries fail or a critical error occurs

def select_top_articles(articles, ticker):
    """Uses Gemini to select the top 5-7 articles from a list."""
    print(f"Selecting top articles for {ticker}...")
    _configure_genai()
    
    # Use the faster "flash" model, which is available on your account
    model = genai.GenerativeModel('models/gemini-flash-latest')
    
    headlines = [f"{idx+1}. {article['title']}" for idx, article in enumerate(articles)]
    prompt = (
        "You are a financial news analyst. From the following list of headlines, "
        "select the top 5 to 7 most significant and impactful articles for an investor "
        f"researching the stock {ticker}. Prioritize specific financial data, "
        "company announcements, or in-depth market analysis. Avoid generic commentary. "
        "Return your answer as a comma-separated list of numbers corresponding to the headlines "
        "(e.g., '1, 3, 5, 8, 12').\n\n"
        "Headlines:\n" + "\n".join(headlines)
    )
    
    selected_indices_str = _call_gemini_with_retry(model, prompt)
    
    if not selected_indices_str:
        print("AI failed to select articles after multiple retries. Falling back to the first 5.")
        return articles[:5]

    try:
        selected_indices = [int(i.strip()) - 1 for i in selected_indices_str.split(',')]
        selected_indices = [i for i in selected_indices if 0 <= i < len(articles)]
        return [articles[i] for i in selected_indices]
    except (ValueError, IndexError):
        print("AI returned an invalid format for selected articles. Falling back to the first 5.")
        return articles[:5]

def generate_summary_with_ai(articles, ticker, history):
    """Uses Gemini to generate a summary from the full text of selected articles."""
    print(f"Generating summary for {ticker}...")
    _configure_genai()
    
    # Use the faster "flash" model
    model = genai.GenerativeModel('models/gemini-flash-latest')

    full_text = "\n\n---\n\n".join(
        f"Article Title: {article['title']}\n\n{article.get('text', 'Content not available.')}" 
        for article in articles
    )
    
    history_context = "\n".join([f"Summary from {item['date']}:\n{item['text']}\n" for item in history]) if history else "No historical summaries available."

    prompt = (
        f"You are an expert financial analyst. Your task is to provide a concise, insightful summary "
        f"of the latest news for the stock {ticker}. The summary must be under 500 words and written "
        f"in a professional, objective tone.\n\n"
        f"Based on the following articles, generate a summary that includes a section titled 'What changed today'.\n\n"
        f"For context, here are the summaries from the past few days:\n{history_context}\n\n"
        f"Here is the full text of today's most important articles:\n{full_text}"
    )
    
    summary = _call_gemini_with_retry(model, prompt)
    
    if not summary:
        return "An error occurred while generating the summary after multiple attempts."
        
    return summary

