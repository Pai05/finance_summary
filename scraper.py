import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from newspaper import Article, ArticleException
import time
from datetime import datetime, timedelta

# --- Helper Functions ---

def get_full_article_text(url):
    """Downloads and parses a URL to get the main article text."""
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except ArticleException:
        print(f"Failed to process article at {url}")
        return None

# --- Scraper Implementations ---

def get_polygon_news(api_key, ticker):
    """Fetches news from the Polygon.io API."""
    articles = []
    # Fetch news from the last 3 days to ensure we have enough content
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    url = f"https://api.polygon.io/v2/reference/news?ticker={ticker}&published_utc.gte={three_days_ago}&limit=20&apiKey={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        for item in data.get('results', []):
            articles.append({
                'title': item['title'],
                'url': item['article_url']
            })
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Polygon.io news: {e}")
    return articles

def get_finviz_news(ticker):
    """Scrapes the news table from a Finviz quote page."""
    articles = []
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        news_table = soup.find(id='news-table')
        if news_table:
            for row in news_table.find_all('tr'):
                link = row.a
                if link:
                    articles.append({
                        'title': link.get_text(),
                        'url': link['href']
                    })
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Finviz news: {e}")
    return articles

def get_tradingview_news(ticker):
    """Scrapes news from TradingView using Selenium for dynamic content."""
    articles = []
    url = f"https://www.tradingview.com/symbols/NYSE-{ticker}/news/" # Adjust for different exchanges if needed
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run browser in the background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)
        time.sleep(5)  # Wait for the news articles to load dynamically

        # Find news items - selector might need updating if TradingView changes their site
        news_elements = driver.find_elements(By.CSS_SELECTOR, 'a[class*="card-"]')
        
        for elem in news_elements[:10]: # Limit to 10 to avoid irrelevant links
            href = elem.get_attribute('href')
            # The title is usually within a nested div
            try:
                title_elem = elem.find_element(By.CSS_SELECTOR, 'span[class*="title-"]')
                title = title_elem.text
                if href and title:
                    articles.append({
                        'title': title,
                        'url': href
                    })
            except Exception:
                continue # Skip if title element is not found
                
        driver.quit()
    except Exception as e:
        print(f"Error fetching TradingView news with Selenium: {e}")
    return articles

# --- Main Consolidator ---

def consolidate_news(api_key, ticker):
    """Collects news from all sources and removes duplicates."""
    all_articles = []
    
    # Run scrapers
    all_articles.extend(get_polygon_news(api_key, ticker))
    all_articles.extend(get_finviz_news(ticker))
    all_articles.extend(get_tradingview_news(ticker))
    
    # Remove duplicates based on URL
    unique_articles = []
    seen_urls = set()
    for article in all_articles:
        if article['url'] not in seen_urls:
            unique_articles.append(article)
            seen_urls.add(article['url'])
            
    return unique_articles

