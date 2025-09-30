import os
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from newspaper import Article, ArticleException, Config
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Helper Functions ---

def get_full_article_text(url):
    """
    Downloads and parses a URL to get the main article text.
    Includes a longer timeout and error handling.
    """
    try:
        # Set a longer timeout and use a common user-agent
        config = Config()
        config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        config.request_timeout = 20  # Increase timeout to 20 seconds

        article = Article(url, config=config)
        article.download()
        article.parse()
        return article.text
    except Exception as e:
        # Catch all exceptions from newspaper3k and print a warning
        print(f"Warning: newspaper3k failed for {url}. Reason: {e}")
        return None

# --- Scraper Implementations ---

def get_polygon_news(ticker):
    """Fetches news from the Polygon.io API."""
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        print("Warning: POLYGON_API_KEY not found in environment variables.")
        return []

    articles = []
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    url = f"https://api.polygon.io/v2/reference/news?ticker={ticker}&published_utc.gte={three_days_ago}&limit=20&apiKey={api_key}"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        for item in data.get('results', []):
            articles.append({'title': item['title'], 'url': item['article_url']})
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Polygon.io news: {e}")
    return articles

def get_finviz_news(ticker):
    """Scrapes the news table from a Finviz quote page."""
    articles = []
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        news_table = soup.find(id='news-table')
        if news_table:
            for row in news_table.find_all('tr'):
                link = row.a
                if link:
                    # Fix for partial URLs
                    href = link['href']
                    if href.startswith('/news/'):
                        href = 'https://finviz.com' + href
                    articles.append({'title': link.get_text(), 'url': href})
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Finviz news: {e}")
    return articles

def get_tradingview_news(ticker):
    """Scrapes news from TradingView using Selenium for dynamic content."""
    articles = []
    
    # Configure Chrome for headless operation on a server
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # Try both NASDAQ and NYSE URLs
    exchanges = ["NASDAQ", "NYSE"]
    found_news = False

    driver = None # Initialize driver to None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        for exchange in exchanges:
            url = f"https://www.tradingview.com/symbols/{exchange}-{ticker}/news/"
            driver.get(url)
            time.sleep(5)

            # Check if the page is valid by looking for a known element
            if "Page not found" in driver.title:
                continue # Try the next exchange

            news_elements = driver.find_elements(By.CSS_SELECTOR, 'a[class*="card-"]')
            if news_elements:
                found_news = True
                for elem in news_elements[:10]:
                    href = elem.get_attribute('href')
                    try:
                        title_elem = elem.find_element(By.CSS_SELECTOR, 'span[class*="title-"]')
                        title = title_elem.text
                        if href and title:
                            articles.append({'title': title, 'url': href})
                    except Exception:
                        continue
                break # Exit loop once news is found
    except Exception as e:
        print(f"Error during Selenium setup or execution: {e}")
    finally:
        if driver:
            driver.quit() # Ensure the browser is always closed

    if not found_news:
        print(f"Could not find a valid TradingView news page for {ticker}.")
        
    return articles

# --- Main Consolidator ---

def consolidate_news(ticker):
    """Collects news from all sources and removes duplicates."""
    all_articles = []
    
    print(f"Collecting news for {ticker}...")
    
    all_articles.extend(get_polygon_news(ticker))
    all_articles.extend(get_finviz_news(ticker))
    all_articles.extend(get_tradingview_news(ticker))
    
    unique_articles = []
    seen_urls = set()
    for article in all_articles:
        if article.get('url') and article['url'] not in seen_urls:
            unique_articles.append(article)
            seen_urls.add(article['url'])
            
    return unique_articles

