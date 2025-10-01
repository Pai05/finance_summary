import os
import sqlite3
import time
import json
from datetime import date, timedelta
from dotenv import load_dotenv

from db_manager import get_db_connection
from scraper import consolidate_news, get_full_article_text
from ai_processor import select_top_articles, generate_summary_with_ai

load_dotenv()

def process_job(job_id, ticker):
    """The main logic for processing a single summarization job."""
    print(f"--- Starting job {job_id} for ticker: {ticker} ---")
    conn = get_db_connection()

    try:
        # Mark job as processing
        conn.execute('UPDATE jobs SET status = "processing" WHERE id = ?', (job_id,))
        conn.commit()
        
        today_str = date.today().isoformat()
        
        # 1. Get historical context
        history = []
        for i in range(1, 8): # last 7 days
            day = date.today() - timedelta(days=i)
            past_summary = conn.execute(
                'SELECT summary_date, summary_text FROM summaries WHERE ticker_symbol = ? AND summary_date = ?',
                (ticker, day.isoformat())
            ).fetchone()
            if past_summary:
                history.append({'date': past_summary['summary_date'], 'text': past_summary['summary_text']})

        # 2. Scrape news
        print(f"Collecting news for {ticker}...")
        all_articles = consolidate_news(ticker)
        if not all_articles:
            raise ValueError(f"No articles found for {ticker}.")

        # 3. AI Step 1: Select top articles
        print(f"Selecting top articles for {ticker}...")
        selected_articles = select_top_articles(all_articles, ticker)
        
        # 4. Get full text for selected articles
        articles_with_text = []
        for article in selected_articles:
            print(f"  - Getting text for: {article['title'][:50]}...")
            try:
                article['text'] = get_full_article_text(article['url'])
                if article['text']:
                    articles_with_text.append(article)
            except Exception as text_exc:
                print(f"  - Warning: Failed to get text for {article['url']}. Reason: {text_exc}")
        
        if not articles_with_text:
            raise ValueError(f"Could not retrieve text for any selected articles for {ticker}.")

        # 5. AI Step 2: Generate summary
        print(f"Generating summary for {ticker}...")
        final_summary = generate_summary_with_ai(articles_with_text, ticker, history)
        
        # 6. Save to database (upsert logic)
        sources_json = json.dumps([{'title': a['title'], 'url': a['url']} for a in articles_with_text])
        
        conn.execute(
            '''
            INSERT INTO summaries (ticker_symbol, summary_date, summary_text, sources) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker_symbol, summary_date) DO UPDATE SET
            summary_text = excluded.summary_text,
            sources = excluded.sources
            ''',
            (ticker, today_str, final_summary, sources_json)
        )
        conn.commit()
        print(f"Successfully generated and saved summary for {ticker}.")

        # Mark job as complete
        conn.execute('UPDATE jobs SET status = "complete" WHERE id = ?', (job_id,))
        conn.commit()

    except Exception as e:
        print(f"!!! An error occurred processing job {job_id} for {ticker}: {e}")
        conn.execute('UPDATE jobs SET status = "failed" WHERE id = ?', (job_id,))
        conn.commit()
    finally:
        conn.close()
        print(f"--- Finished job {job_id} for {ticker} ---")

def main_loop():
    """The main worker loop that checks for pending jobs."""
    print("Starting background worker...")
    while True:
        conn = get_db_connection()
        job = conn.execute(
            "SELECT id, ticker_symbol FROM jobs WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        conn.close()
        
        if job:
            process_job(job['id'], job['ticker_symbol'])
        else:
            # If no jobs, wait before checking again
            time.sleep(10) 

if __name__ == '__main__':
    # Initialize the DB schema just in case
    from db_manager import init_db
    init_db()
    main_loop()
