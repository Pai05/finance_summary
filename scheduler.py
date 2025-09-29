import os
import sqlite3
import json
from datetime import date, timedelta
from dotenv import load_dotenv
from scraper import consolidate_news, get_full_article_text
from ai_processor import select_top_articles, generate_summary
from db_manager import get_db_connection

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def run_daily_job():
    """
    The main job to be run daily. It fetches all tickers from the DB,
    generates a new summary for each, and saves it.
    """
    print("Starting daily summary generation job...")
    conn = get_db_connection()
    tickers = conn.execute('SELECT symbol FROM tickers').fetchall()
    conn.close() # Close connection after fetching tickers

    if not tickers:
        print("No tickers in the database. Exiting job.")
        return

    today_str = date.today().isoformat()
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()

    for ticker_row in tickers:
        ticker = ticker_row['symbol']
        print(f"--- Processing ticker: {ticker} ---")

        conn = get_db_connection()
        
        # 1. Check if a summary for today already exists
        exists = conn.execute(
            'SELECT 1 FROM summaries WHERE ticker_symbol = ? AND summary_date = ?',
            (ticker, today_str)
        ).fetchone()

        if exists:
            print(f"Summary for {ticker} already exists for today. Skipping.")
            conn.close()
            continue
        
        # 2. Get yesterday's summary for historical context
        historical_summary_row = conn.execute(
            'SELECT summary_text FROM summaries WHERE ticker_symbol = ? AND summary_date = ?',
            (ticker, yesterday_str)
        ).fetchone()
        historical_summary = historical_summary_row['summary_text'] if historical_summary_row else None
        
        try:
            # 3. Scrape news
            print(f"Collecting news for {ticker}...")
            all_articles = consolidate_news(POLYGON_API_KEY, ticker)
            if not all_articles:
                print(f"No articles found for {ticker}. Moving to next ticker.")
                conn.close()
                continue

            # 4. AI Step 1: Select top articles
            print("Selecting top articles...")
            selected_titles = select_top_articles(GEMINI_API_KEY, all_articles, ticker)
            selected_articles = [article for article in all_articles if article['title'] in selected_titles]
            
            # 5. Get full text for selected articles
            articles_with_text = []
            for article in selected_articles:
                print(f"  - Getting text for: {article['title'][:50]}...")
                article['text'] = get_full_article_text(article['url'])
                if article['text']:
                    articles_with_text.append(article)
            
            if not articles_with_text:
                print(f"Could not retrieve text for any articles for {ticker}. Moving on.")
                conn.close()
                continue
            
            # 6. AI Step 2: Generate final summary
            print("Generating final summary...")
            final_summary = generate_summary(GEMINI_API_KEY, articles_with_text, ticker, historical_summary)
            
            # 7. Save to database
            sources_json = json.dumps([{'title': a['title'], 'url': a['url']} for a in articles_with_text])
            
            conn.execute(
                'INSERT INTO summaries (ticker_symbol, summary_date, summary_text, sources) VALUES (?, ?, ?, ?)',
                (ticker, today_str, final_summary, sources_json)
            )
            conn.commit()
            print(f"Successfully generated and saved summary for {ticker}.")

        except Exception as e:
            print(f"!!! An error occurred processing {ticker}: {e}")
        finally:
            conn.close()
            print(f"--- Finished processing {ticker} ---")

    print("Daily summary generation job finished.")

if __name__ == '__main__':
    run_daily_job()

 
