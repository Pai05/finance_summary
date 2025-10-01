import os
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from newspaper import Article, ArticleException, Config
import time
from datetime import datetime, timedelta
import uuid # Import the uuid module to generate unique IDs

# --- Helper Functions ---

def get_full_article_text(url):
    """Downloads and parses a URL to get the main article text."""
    try:
        config = Config()
        config.request_timeout = 20
        
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
    """Scrapes news from TradingView using Selenium for dynamic content."""
    articles = []
    driver = None # Initialize driver to None

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920x1080")
        
        user_data_dir = f"/tmp/chrome-user-data-{uuid.uuid4()}"
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

        # **FINAL PRODUCTION FIX: More robust check for Render environment**
        chrome_driver_path = "/usr/bin/chromedriver"
        if os.path.exists(chrome_driver_path):
            print("Production environment detected. Using explicit driver path.")
            chrome_options.binary_location = "/usr/bin/google-chrome"
            service = Service(executable_path=chrome_driver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else: # For local development
            print("Local development environment detected. Using automatic driver setup.")
            driver = webdriver.Chrome(options=chrome_options)

        exchanges = ["NASDAQ", "NYSE"]
        for exchange in exchanges:
            url = f"https://www.tradingview.com/symbols/{exchange}-{ticker}/news/"
            try:
                driver.get(url)
                time.sleep(5)
                
                news_elements = driver.find_elements(By.CSS_SELECTOR, 'a[class*="card-"]')
                if news_elements:
                    for elem in news_elements[:10]:
                        try:
                            href = elem.get_attribute('href')
                            title_elem = elem.find_element(By.CSS_SELECTOR, 'span[class*="title-"]')
                            title = title_elem.text
                            if href and title:
                                articles.append({'title': title, 'url': href})
                        except Exception:
                            continue
                    break 
            except Exception:
                continue
    
    except Exception as e:
        print(f"Error during Selenium setup or execution: {e}")
        
    finally:
        if driver:
            driver.quit()
            
    return articles

# --- Main Consolidator ---

def consolidate_news(ticker):
    """Collects news from all sources and removes duplicates."""
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
            
    return unique_articles

