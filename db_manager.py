import sqlite3

def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema."""
    conn = get_db_connection()
    print("Initializing database...")

    # Table for storing user-added tickers
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL
        );
    ''')

    # Table for storing daily summaries
    conn.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker_symbol TEXT NOT NULL,
            summary_date DATE NOT NULL,
            summary_text TEXT NOT NULL,
            sources TEXT, -- Storing sources as a JSON string
            UNIQUE(ticker_symbol, summary_date)
        );
    ''')

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == '__main__':
    init_db()

 
