import os
import google.generativeai as genai

def configure_genai():
    """Configures the Gemini AI with the API key."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)

def select_top_articles(articles, ticker):
    """Uses Gemini to select the top 5-7 articles from a list."""
    print(f"Selecting top articles for {ticker}...")
    configure_genai()
    
    # **FIX: Use the 'gemini-pro-latest' model**
    model = genai.GenerativeModel('gemini-pro-latest')
    
    headlines = [f"{idx+1}. {article['title']}" for idx, article in enumerate(articles)]
    prompt = (
        "You are a financial news analyst. From the following list of headlines, "
        "select the top 5 to 7 most significant and impactful articles for an investor "
        f"researching the stock {ticker}. Prioritize articles with specific financial data, "
        "company announcements, or in-depth market analysis. Avoid generic market commentary. "
        "Return your answer as a comma-separated list of numbers corresponding to the headlines "
        "(e.g., '1, 3, 5, 8, 12').\n\n"
        "Headlines:\n" + "\n".join(headlines)
    )
    
    try:
        response = model.generate_content(prompt)
        selected_indices_str = response.text.strip()
        selected_indices = [int(i.strip()) - 1 for i in selected_indices_str.split(',')]
        
        # Filter to ensure indices are valid
        selected_indices = [i for i in selected_indices if 0 <= i < len(articles)]
        
        return [articles[i] for i in selected_indices]
    except Exception as e:
        print(f"Error selecting articles with Gemini: {e}")
        # As a fallback, return the first 5 articles
        return articles[:5]

def generate_summary_with_ai(articles, ticker, history):
    """Uses Gemini to generate a summary from the full text of selected articles."""
    print(f"Generating summary for {ticker}...")
    configure_genai()
    
    # **FIX: Use the 'gemini-pro-latest' model**
    model = genai.GenerativeModel('gemini-pro-latest')

    full_text = "\n\n---\n\n".join(
        f"Article Title: {article['title']}\n\n{article.get('text', 'Content not available.')}" 
        for article in articles
    )
    
    history_context = "\n".join([f"Summary from {item['date']}:\n{item['summary']}\n" for item in history])

    prompt = (
        f"You are an expert financial analyst. Your task is to provide a concise, insightful summary "
        f"of the latest news for the stock {ticker}. The summary must be under 500 words and written "
        f"in a professional, objective tone.\n\n"
        f"Based on the following articles, generate a summary that includes a section titled 'What changed today'.\n\n"
        f"For context, here are the summaries from the past few days:\n{history_context}\n\n"
        f"Here is the full text of today's most important articles:\n{full_text}"
    )
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating summary with Gemini: {e}")
        return "An error occurred while generating the summary."

