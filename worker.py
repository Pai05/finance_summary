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

def process_job(job):
    """Processes a single job from the database."""
    ticker = job['ticker_symbol']
    job_id = job['id']
    conn = get_db_connection()

    try:
        print(f"--- Processing job {job_id} for ticker: {ticker} ---")
        
        conn.execute("UPDATE jobs SET status = 'processing' WHERE id = ?", (job_id,))
        conn.commit()

        today_str = date.today().isoformat()
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        
        historical_summary_row = conn.execute(
            'SELECT summary_text FROM summaries WHERE ticker_symbol = ? AND summary_date = ?',
            (ticker, yesterday_str)
        ).fetchone()
        historical_summary = historical_summary_row['summary_text'] if historical_summary_row else None
        
        print(f"Collecting news for {ticker}...")
        all_articles = consolidate_news(ticker)
        
        if not all_articles:
            raise Exception(f"No articles found for {ticker}.")

        print(f"Selecting top articles for {ticker}...")
        selected_articles = select_top_articles(all_articles, ticker)
        
        articles_with_text = []
        for article in selected_articles:
            article['text'] = get_full_article_text(article['url'])
            if article['text']:
                articles_with_text.append(article)
        
        if not articles_with_text:
            raise Exception("Could not retrieve text for any selected articles.")

        print(f"Generating summary for {ticker}...")
        final_summary = generate_summary_with_ai(articles_with_text, ticker, historical_summary)
        
        sources_json = json.dumps([{'title': a['title'], 'url': a['url']} for a in articles_with_text])
        
        conn.execute(
            'INSERT INTO summaries (ticker_symbol, summary_date, summary_text, sources) VALUES (?, ?, ?, ?)',
            (ticker, today_str, final_summary, sources_json)
        )
        
        conn.execute("UPDATE jobs SET status = 'complete' WHERE id = ?", (job_id,))
        conn.commit()
        print(f"--- Successfully completed job {job_id} for {ticker} ---")

    except Exception as e:
        print(f"!!! CRITICAL ERROR processing job {job_id} for {ticker}: {e}")
        conn.execute("UPDATE jobs SET status = 'failed' WHERE id = ?", (job_id,))
        conn.commit()
    finally:
        conn.close()

def main():
    """The main worker function, designed to run once."""
    print("Starting cron job worker...")
    conn = get_db_connection()
    job_to_process = conn.execute(
        "SELECT * FROM jobs WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    conn.close()

    if job_to_process:
        print(f"Found pending job {job_to_process['id']}. Processing...")
        process_job(job_to_process)
    else:
        print("No pending jobs found. Exiting.")

if __name__ == '__main__':
    main()

