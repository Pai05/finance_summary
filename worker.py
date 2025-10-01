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

def process_single_job():
    """
    Finds and processes a single pending job from the database.
    This function is designed to be completely resilient.
    """
    conn = None
    job_to_process = None
    
    try:
        # --- Find a job to process ---
        print("Worker starting: looking for a pending job...")
        conn = get_db_connection()
        job_to_process = conn.execute(
            "SELECT * FROM jobs WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()

        if not job_to_process:
            print("No pending jobs found. Worker exiting.")
            return

        job_id = job_to_process['id']
        ticker = job_to_process['ticker_symbol']
        print(f"--- Found job {job_id} for ticker: {ticker}. Starting processing. ---")
        
        # --- Mark job as 'processing' ---
        conn.execute("UPDATE jobs SET status = 'processing' WHERE id = ?", (job_id,))
        conn.commit()

        # --- Main processing logic ---
        today_str = date.today().isoformat()
        
        # Get historical context
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        historical_summary_row = conn.execute(
            'SELECT summary_text FROM summaries WHERE ticker_symbol = ? AND summary_date = ?',
            (ticker, yesterday_str)
        ).fetchone()
        historical_summary = historical_summary_row['summary_text'] if historical_summary_row else None

        # Scrape news
        print(f"Collecting news for {ticker}...")
        all_articles = consolidate_news(ticker)
        if not all_articles:
            raise Exception(f"No articles found for {ticker}.")

        # AI Step 1: Select articles
        print(f"Selecting top articles for {ticker}...")
        selected_articles = select_top_articles(all_articles, ticker)
        if not selected_articles:
            raise Exception("AI failed to select any articles.")

        # Get full article text
        articles_with_text = []
        for article in selected_articles:
            article['text'] = get_full_article_text(article['url'])
            if article['text']:
                articles_with_text.append(article)
        
        if not articles_with_text:
            raise Exception("Could not retrieve text for any selected articles.")

        # AI Step 2: Generate summary
        print(f"Generating summary for {ticker}...")
        final_summary = generate_summary_with_ai(articles_with_text, ticker, historical_summary)
        
        # Save results
        sources_json = json.dumps([{'title': a['title'], 'url': a['url']} for a in articles_with_text])
        conn.execute(
            'INSERT INTO summaries (ticker_symbol, summary_date, summary_text, sources) VALUES (?, ?, ?, ?)',
            (ticker, today_str, final_summary, sources_json)
        )
        
        # --- Mark job as 'complete' ---
        conn.execute("UPDATE jobs SET status = 'complete' WHERE id = ?", (job_id,))
        conn.commit()
        print(f"--- Successfully completed job {job_id} for {ticker} ---")

    except Exception as e:
        # --- This is the critical error handler ---
        print(f"!!! A CRITICAL ERROR occurred: {e}")
        # If a job was being processed, mark it as 'failed'
        if conn and job_to_process:
            job_id = job_to_process['id']
            print(f"Marking job {job_id} as 'failed'.")
            try:
                conn.execute("UPDATE jobs SET status = 'failed' WHERE id = ?", (job_id,))
                conn.commit()
            except Exception as db_err:
                print(f"Could not update job status to failed. DB Error: {db_err}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # This ensures the script runs the main function and exits.
    process_single_job()

