import os
import requests
from bs4 import BeautifulSoup
from newspaper import Article, ArticleException, Config
import time
from datetime import datetime, timedelta

# --- Helper Functions ---

def get_full_article_text(url):
    """Downloads and parses a URL to get the main article text."""
    try:
        config = Config()
        config.request_timeout = 20 # 20 seconds
        
        article = Article(url, config=config)
        article.download()
        article.parse()
        return article.text
    except Exception as e:
        print(f"Warning: newspaper3k failed for {url}. Reason: {e}")
        return None

# --- Scraper Implementations ---

def get_polygon_news(ticker):
    """Fetches news from the Polygon.io API."""
    api_key = os.getenv("POLYGON_API_KEY")
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
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        news_table = soup.find(id='news-table')
        if news_table:
            for row in news_table.find_all('tr'):
                link = row.a
                if link:
                    href = link['href']
                    if href.startswith('/news/'):
                        href = 'https://finviz.com' + href
                    articles.append({'title': link.get_text(), 'url': href})
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Finviz news: {e}")
    return articles

def get_tradingview_news(ticker):
    """
    Scrapes news from TradingView using a lightweight requests/BeautifulSoup method.
    This completely replaces the slow and heavy Selenium implementation.
    """
    articles = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    exchanges = ["NASDAQ", "NYSE"]
    for exchange in exchanges:
        url = f"https://www.tradingview.com/symbols/{exchange}-{ticker}/news/"
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            # Find news items by looking for links with a specific data-widget-name attribute
            news_elements = soup.find_all('a', {'data-widget-name': 'news-item-card-header'})

            if news_elements:
                for elem in news_elements[:10]:
                    href = elem.get('href')
                    # The title is the text content of the link
                    title = elem.get_text(strip=True)
                    if href and title:
                        # Ensure the URL is absolute
                        if not href.startswith('http'):
                            href = 'https://www.tradingview.com' + href
                        articles.append({'title': title, 'url': href})
                return articles # Return as soon as we find news on one exchange
        except requests.exceptions.RequestException as e:
            print(f"Could not fetch TradingView news for {ticker} on {exchange}: {e}")
            continue # Try the next exchange
    
    print(f"Could not find any TradingView news for {ticker} on any exchange.")
    return articles

# --- Main Consolidator ---

def consolidate_news(ticker):
    """Collects news from all sources and removes duplicates."""
    print(f"Collecting news for {ticker}...")
    all_articles = []
    
    all_articles.extend(get_polygon_news(ticker))
    all_articles.extend(get_finviz_news(ticker))
    all_articles.extend(get_tradingview_news(ticker))
    
    unique_articles = []
    seen_urls = set()
    for article in all_articles:
        if article.get('url') and article['url'] not in seen_urls:
            unique_articles.append(article)
            seen_urls.add(article['url'])
            
    if not unique_articles:
        print(f"No articles found for {ticker}.")

    return unique_articles

