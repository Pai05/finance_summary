import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
from scraper import consolidate_news, get_full_article_text
from ai_processor import select_top_articles, generate_summary_with_ai
from db_manager import get_db_connection
from datetime import date, timedelta
import json

# Load environment variables from .env file at the start
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    
    # Handle the form submission for adding a new ticker
    if request.method == 'POST':
        ticker = request.form['ticker'].upper().strip()
        if ticker:
            try:
                # Add the new ticker to the database; ignore if it already exists
                conn.execute('INSERT OR IGNORE INTO tickers (symbol) VALUES (?)', (ticker,))
                conn.commit()
            except sqlite3.Error as e:
                print(f"Database error on insert: {e}")
        return redirect(url_for('index', ticker=ticker))

    # Fetch all tracked tickers to display in the sidebar
    tickers = conn.execute('SELECT symbol FROM tickers ORDER BY symbol').fetchall()
    
    # Determine which ticker is currently selected
    selected_ticker = request.args.get('ticker')
    if not selected_ticker and tickers:
        selected_ticker = tickers[0]['symbol']
    
    # Fetch historical summaries for the selected ticker
    summaries = []
    if selected_ticker:
        today = date.today()
        for i in range(8): # Fetch today + the last 7 days
            current_date = today - timedelta(days=i)
            summary_data = conn.execute(
                'SELECT summary_date, summary_text, sources FROM summaries WHERE ticker_symbol = ? AND summary_date = ?',
                (selected_ticker, current_date.isoformat())
            ).fetchone()
            
            if summary_data:
                try:
                    # The 'sources' column is a JSON string; parse it into a Python list
                    sources_list = json.loads(summary_data['sources'])
                except (json.JSONDecodeError, TypeError):
                    sources_list = [] # Default to an empty list if parsing fails
                
                summaries.append({
                    'date': summary_data['summary_date'],
                    'text': summary_data['summary_text'],
                    'sources': sources_list
                })
    conn.close()
    
    # Render the main page with all the necessary data
    return render_template('index.html', 
                           tickers=tickers, 
                           selected_ticker=selected_ticker, 
                           summaries=summaries)

@app.route('/refresh/<ticker>')
def refresh_ticker(ticker):
    """Manually triggers a news scrape and AI summary generation for a specific ticker."""
    print(f"--- Manual refresh triggered for {ticker} ---")
    conn = get_db_connection()
    
    try:
        # 1. Get the summary from the previous day to provide context to the AI
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        historical_row = conn.execute(
            'SELECT summary_text FROM summaries WHERE ticker_symbol = ? AND summary_date = ?',
            (ticker, yesterday_str)
        ).fetchone()
        historical_summary = historical_row['summary_text'] if historical_row else None

        # 2. Scrape all news sources
        print(f"Collecting news for {ticker}...")
        all_articles = consolidate_news(ticker) # No need to pass API key here
        
        if not all_articles:
            print(f"No articles found for {ticker}.")
            return redirect(url_for('index', ticker=ticker))

        # 3. AI Step 1: Select the most important articles
        # This function now correctly returns a list of article DICTIONARIES
        selected_articles = select_top_articles(all_articles, ticker)
        
        # 4. Get the full text for only the selected articles
        articles_with_text = []
        for article in selected_articles:
            print(f"Getting full text for: {article['url']}")
            article_text = get_full_article_text(article['url'])
            if article_text:
                article['text'] = article_text # Add the full text to the dictionary
                articles_with_text.append(article)
        
        if not articles_with_text:
            print(f"Could not retrieve text for any selected articles for {ticker}.")
            return redirect(url_for('index', ticker=ticker))

        # 5. AI Step 2: Generate the final summary using the full text
        final_summary = generate_summary_with_ai(articles_with_text, ticker, historical_summary)
        
        # 6. Save the new summary and its sources to the database
        sources_json = json.dumps([{'title': a['title'], 'url': a['url']} for a in articles_with_text])
        today_str = date.today().isoformat()
        
        # Use INSERT OR REPLACE to either add a new summary or update an existing one for today
        conn.execute(
            'INSERT OR REPLACE INTO summaries (ticker_symbol, summary_date, summary_text, sources) VALUES (?, ?, ?, ?)',
            (ticker, today_str, final_summary, sources_json)
        )
        conn.commit()
        print(f"Successfully saved summary for {ticker}.")

    except Exception as e:
        print(f"!!! An unexpected error occurred in refresh_ticker for {ticker}: {e}")
    finally:
        conn.close()

    return redirect(url_for('index', ticker=ticker))

if __name__ == '__main__':
    app.run(debug=True)

