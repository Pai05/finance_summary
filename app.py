 
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
from scraper import consolidate_news, get_full_article_text
from ai_processor import select_top_articles, generate_summary_with_ai
from db_manager import get_db_connection
from datetime import date, timedelta
import json

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    
    # Handle adding a new ticker
    if request.method == 'POST':
        ticker = request.form['ticker'].upper().strip()
        if ticker:
            try:
                conn.execute('INSERT INTO tickers (symbol) VALUES (?)', (ticker,))
                conn.commit()
            except sqlite3.IntegrityError:
                # Ticker already exists, do nothing
                pass
        return redirect(url_for('index'))

    # Get data for display
    tickers = conn.execute('SELECT symbol FROM tickers ORDER BY symbol').fetchall()
    
    selected_ticker = request.args.get('ticker')
    if not selected_ticker and tickers:
        selected_ticker = tickers[0]['symbol']
    
    today = date.today()
    summaries = []
    
    if selected_ticker:
        # Fetch summaries for the last 7 days + today
        for i in range(8):
            current_date = today - timedelta(days=i)
            summary_data = conn.execute(
                'SELECT summary_date, summary_text, sources FROM summaries WHERE ticker_symbol = ? AND summary_date = ?',
                (selected_ticker, current_date.isoformat())
            ).fetchone()
            if summary_data:
                # Safely parse JSON sources
                try:
                    sources_list = json.loads(summary_data['sources'])
                except (json.JSONDecodeError, TypeError):
                    sources_list = [] # Default to empty list on error
                
                summaries.append({
                    'date': summary_data['summary_date'],
                    'text': summary_data['summary_text'],
                    'sources': sources_list
                })

    conn.close()
    
    return render_template('index.html', 
                           tickers=tickers, 
                           selected_ticker=selected_ticker, 
                           summaries=summaries)

@app.route('/refresh/<ticker>')
def refresh_ticker(ticker):
    """Manually triggers a refresh for a specific ticker."""
    print(f"Manual refresh triggered for {ticker}")
    conn = get_db_connection()
    today_str = date.today().isoformat()

    # 1. Check if summary for today already exists
    exists = conn.execute(
        'SELECT 1 FROM summaries WHERE ticker_symbol = ? AND summary_date = ?',
        (ticker, today_str)
    ).fetchone()

    if exists:
        print(f"Summary for {ticker} on {today_str} already exists. Skipping.")
        conn.close()
        return redirect(url_for('index', ticker=ticker))

    # 2. Fetch historical summary for context
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()
    historical_summary_row = conn.execute(
        'SELECT summary_text FROM summaries WHERE ticker_symbol = ? AND summary_date = ?',
        (ticker, yesterday_str)
    ).fetchone()
    historical_summary = historical_summary_row['summary_text'] if historical_summary_row else None

    # 3. Scrape and Process
    try:
        print(f"Collecting news for {ticker}...")
        all_articles = consolidate_news(POLYGON_API_KEY, ticker)
        
        if not all_articles:
            print(f"No articles found for {ticker}.")
            conn.close()
            return redirect(url_for('index', ticker=ticker))

        print(f"Selecting top articles for {ticker}...")
        selected_titles = select_top_articles(GEMINI_API_KEY, all_articles, ticker)
        
        selected_articles = [article for article in all_articles if article['title'] in selected_titles]
        
        articles_with_text = []
        for article in selected_articles:
            print(f"Getting full text for: {article['url']}")
            article['text'] = get_full_article_text(article['url'])
            if article['text']:
                articles_with_text.append(article)
        
        if not articles_with_text:
            print(f"Could not retrieve text for any selected articles for {ticker}.")
            conn.close()
            return redirect(url_for('index', ticker=ticker))

        print(f"Generating summary for {ticker}...")
        final_summary = generate_summary_with_ai(GEMINI_API_KEY, articles_with_text, ticker, historical_summary)
        
        # 4. Save to DB
        sources_json = json.dumps([{'title': a['title'], 'url': a['url']} for a in articles_with_text])
        
        conn.execute(
            'INSERT INTO summaries (ticker_symbol, summary_date, summary_text, sources) VALUES (?, ?, ?, ?)',
            (ticker, today_str, final_summary, sources_json)
        )
        conn.commit()
        print(f"Successfully saved summary for {ticker}.")

    except Exception as e:
        print(f"An error occurred while refreshing {ticker}: {e}")
    finally:
        conn.close()

    return redirect(url_for('index', ticker=ticker))

if __name__ == '__main__':
    app.run(debug=True)

