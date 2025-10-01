import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify
from dotenv import load_dotenv
from db_manager import get_db_connection
from datetime import date, timedelta
import json

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    
    if request.method == 'POST':
        ticker = request.form['ticker'].upper().strip()
        if ticker:
            try:
                conn.execute('INSERT INTO tickers (symbol) VALUES (?)', (ticker,))
                conn.commit()
            except sqlite3.IntegrityError:
                pass # Ticker already exists
        return redirect(url_for('index', ticker=ticker))

    tickers = conn.execute('SELECT symbol FROM tickers ORDER BY symbol').fetchall()
    selected_ticker = request.args.get('ticker')
    if not selected_ticker and tickers:
        selected_ticker = tickers[0]['symbol']
    
    summaries = []
    processing_job = False
    
    if selected_ticker:
        # Check if there is a pending or processing job for this ticker
        job_status = conn.execute(
            "SELECT status FROM jobs WHERE ticker_symbol = ? AND (status = 'pending' OR status = 'processing') ORDER BY created_at DESC LIMIT 1",
            (selected_ticker,)
        ).fetchone()
        if job_status:
            processing_job = True

        # Fetch summaries for the last 7 days
        for i in range(7):
            current_date = date.today() - timedelta(days=i)
            summary_data = conn.execute(
                'SELECT summary_date, summary_text, sources FROM summaries WHERE ticker_symbol = ? AND summary_date = ?',
                (selected_ticker, current_date.isoformat())
            ).fetchone()
            if summary_data:
                try:
                    sources_list = json.loads(summary_data['sources']) if summary_data['sources'] else []
                except (json.JSONDecodeError, TypeError):
                    sources_list = []
                
                summaries.append({
                    'date': summary_data['summary_date'],
                    'text': summary_data['summary_text'],
                    'sources': sources_list
                })

    conn.close()
    
    return render_template('index.html', 
                           tickers=tickers, 
                           selected_ticker=selected_ticker, 
                           summaries=summaries,
                           processing_job=processing_job)

@app.route('/refresh/<ticker>')
def refresh_ticker(ticker):
    """Creates a new job to refresh a ticker's summary."""
    conn = get_db_connection()
    today_str = date.today().isoformat()

    # Clear out any old failed jobs for this ticker
    conn.execute("DELETE FROM jobs WHERE ticker_symbol = ? AND status = 'failed'", (ticker,))
    
    # Check if a summary for today already exists
    exists = conn.execute(
        'SELECT 1 FROM summaries WHERE ticker_symbol = ? AND summary_date = ?',
        (ticker, today_str)
    ).fetchone()
    
    # Check if a pending/processing job already exists
    job_exists = conn.execute(
        "SELECT 1 FROM jobs WHERE ticker_symbol = ? AND (status = 'pending' OR status = 'processing')",
        (ticker,)
    ).fetchone()

    if exists or job_exists:
        print(f"Skipping job creation for {ticker}: already exists or is in progress.")
    else:
        print(f"Creating new refresh job for {ticker}")
        conn.execute('INSERT INTO jobs (ticker_symbol) VALUES (?)', (ticker,))
    
    conn.commit()
    conn.close()
    return redirect(url_for('index', ticker=ticker))

@app.route('/status/<ticker>')
def job_status(ticker):
    """API endpoint for the frontend to check if a job is complete."""
    conn = get_db_connection()
    job = conn.execute(
        "SELECT status FROM jobs WHERE ticker_symbol = ? ORDER BY created_at DESC LIMIT 1",
        (ticker,)
    ).fetchone()
    conn.close()
    
    if job and job['status'] in ['complete', 'failed']:
        return jsonify({'status': 'complete'})
    else:
        return jsonify({'status': 'processing'})

if __name__ == '__main__':
    app.run(debug=True)

