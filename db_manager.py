import sqlite3

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database with the required tables."""
    conn = get_db_connection()
    
    # Create tickers table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL
        )
    ''')
    
    # Create summaries table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker_symbol TEXT NOT NULL,
            summary_date DATE NOT NULL,
            summary_text TEXT NOT NULL,
            sources TEXT,
            UNIQUE(ticker_symbol, summary_date)
        )
    ''')
    
    # Create the new jobs table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker_symbol TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', -- pending, processing, complete, failed
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized with tickers, summaries, and jobs tables.")

if __name__ == '__main__':
    init_db()

