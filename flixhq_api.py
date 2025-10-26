#!/usr/bin/env python3

from flask import Flask, jsonify, request
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import logging
import re
import os
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


class FlixHQAPI:
    
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-setuid-sandbox')
        
        possible_chrome_paths = [
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            os.getenv('GOOGLE_CHROME_BIN'),
        ]
        
        chrome_binary = None
        for path in possible_chrome_paths:
            if path and os.path.exists(path):
                chrome_binary = path
                break
        
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            logger.info(f"✓ Chrome spotted at: {chrome_binary}")
        
        user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
        ]
        chrome_options.add_argument(f'user-agent={random.choice(user_agents)}')
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            self.driver.set_page_load_timeout(30)
            logger.info("✓ Chrome ready to scrape! 🎬")
        except Exception as e1:
            logger.warning(f"ChromeDriverManager failed: {e1}")
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.set_page_load_timeout(30)
                logger.info("✓ Using system chromedriver")
            except Exception as e2:
                logger.error(f"Chrome init failed completely: {e2}")
                sys.exit(1)
    
    def scrape_home(self, limit=20):
        try:
            url = "https://flixhq-tv.lol/home"
            logger.info(f"🏠 Visiting home page...")
            self.driver.get(url)
            time.sleep(random.uniform(2, 3))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = self._extract_items(soup)
            
            logger.info(f"✓ Grabbed {len(items)} movies! 🍿")
            return items[:limit] if limit else items
        except Exception as e:
            logger.error(f"❌ Home scraping failed: {e}")
            return []
    
    def search(self, keyword, limit=20):
        try:
            search_url = f"https://flixhq-tv.lol/search/{keyword.replace(' ', '-')}"
            logger.info(f"🔍 Searching for: {keyword}")
            self.driver.get(search_url)
            time.sleep(random.uniform(2, 3))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = self._extract_items(soup)
            
            logger.info(f"✓ Found {len(items)} results! 🎯")
            return items[:limit] if limit else items
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []
    
    def get_details_with_servers(self, movie_url):
        try:
            logger.info(f"📽️ Getting movie with stream sources...")
            self.driver.get(movie_url)
            time.sleep(5)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            details = self._extract_basic_details(soup)
            
            stream_sources = []
            
            logger.info("🎥 Looking for ALL server buttons (debug mode)...")
            
            time.sleep(3)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            try:
                server_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                    'a[data-id], button[data-id], li[data-id], div[data-id]')
                
                logger.info(f"Found {len(server_buttons)} buttons with data-id")
                
                for idx, button in enumerate(server_buttons):
                    try:
                        button_text = button.text.strip()
                        data_id = button.get_attribute('data-id')
                        
                        logger.info(f"🔍 Button {idx+1}: text='{button_text}', data-id='{data_id}'")
                        
                        if not data_id:
                            continue
                        
                        if button_text:
                            logger.info(f"🎬 Clicking button '{button_text}'...")
                            
                            try:
                                self.driver.execute_script("arguments[0].click();", button)
                                time.sleep(4)
                                
                                current_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                                iframe = current_soup.find('iframe')
                                
                                if iframe:
                                    iframe_src = iframe.get('src') or iframe.get('data-src')
                                    if iframe_src:
                                        if not iframe_src.startswith('http'):
                                            iframe_src = f"https:{iframe_src}" if iframe_src.startswith('//') else iframe_src
                                        
                                        server_name = button_text or 'Unknown Server'
                                        
                                        stream_sources.append({
                                            'server': server_name,
                                            'url': iframe_src,
                                            'type': 'iframe'
                                        })
                                        
                                        logger.info(f"✓ Got {server_name} stream! 🎉")
                                else:
                                    logger.warning(f"⚠️ No iframe found after clicking {button_text}")
                            
                            except Exception as click_err:
                                logger.warning(f"⚠️ Failed to click {button_text}: {click_err}")
                    
                    except Exception as btn_err:
                        logger.warning(f"⚠️ Button error: {btn_err}")
                        continue
            
            except Exception as selenium_err:
                logger.error(f"❌ Server extraction failed: {selenium_err}")
            
            unique_sources = []
            seen_urls = set()
            for source in stream_sources:
                if source['url'] not in seen_urls:
                    seen_urls.add(source['url'])
                    unique_sources.append(source)
            
            details['sources'] = unique_sources
            details['source_count'] = len(unique_sources)
            
            logger.info(f"🎉 Total sources found: {len(unique_sources)}")
            
            return details
            
        except Exception as e:
            logger.error(f"❌ Details extraction failed: {e}")
            return {
                'description': None,
                'year': None,
                'rating': None,
                'sources': [],
                'source_count': 0,
                'error': str(e)
            }
    
    def _extract_basic_details(self, soup):
        details = {}
        
        desc_elem = soup.find(class_=lambda x: x and 'description' in str(x).lower())
        if desc_elem:
            details['description'] = desc_elem.get_text(strip=True)[:500]
        else:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            details['description'] = meta_desc.get('content', None) if meta_desc else None
        
        year_elem = soup.find(class_=lambda x: x and 'year' in str(x).lower())
        if year_elem:
            year_match = re.search(r'\b(19\d{2}|20[0-3]\d)\b', year_elem.get_text())
            details['year'] = year_match.group(1) if year_match else None
        else:
            details['year'] = None
        
        rating_elem = soup.find(class_=lambda x: x and ('rating' in str(x).lower() or 'imdb' in str(x).lower()))
        if rating_elem:
            rating_match = re.search(r'(\d+\.?\d*)', rating_elem.get_text())
            details['rating'] = rating_match.group(1) if rating_match else None
        else:
            details['rating'] = None
        
        return details
    
    def _extract_items(self, soup):
        items = []
        containers = soup.find_all('div', class_='flw-item')
        if not containers:
            containers = soup.find_all('div', class_='film-poster')
        if not containers:
            all_links = soup.find_all('a', href=True)
            containers = [link for link in all_links if link.find('img')]
        
        for container in containers:
            item = self._parse_item(container)
            if item:
                items.append(item)
        
        return items
    
    def _parse_item(self, container):
        try:
            item = {}
            
            link = container if container.name == 'a' else container.find('a', href=True)
            if link and link.get('href'):
                item['link'] = link['href']
                if not item['link'].startswith('http'):
                    item['link'] = f"https://flixhq-tv.lol{item['link']}"
            else:
                return None
            
            title = link.get('title') or link.get('data-tip')
            if not title:
                title_elem = container.find(['h2', 'h3'])
                title = title_elem.get_text(strip=True) if title_elem else None
            if not title:
                img = container.find('img')
                title = img.get('alt') if img else None
            
            if not title:
                return None
            
            item['title'] = title
            
            img = container.find('img')
            item['thumbnail'] = img.get('data-src') or img.get('src') if img else None
            
            item['type'] = 'movie' if '/movie/' in item['link'] else 'tv' if '/tv/' in item['link'] else 'unknown'
            
            return item
        except:
            return None
    
    def close(self):
        if self.driver:
            self.driver.quit()
            logger.info("✓ Chrome closed, peace out! 👋")


scraper = None

def get_scraper():
    global scraper
    if scraper is None:
        scraper = FlixHQAPI()
    return scraper


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'name': 'FlixHQ API',
        'version': '3.1.0 DEBUG',
        'message': '🎬 Debug mode - extracts ALL servers!',
        'endpoints': {
            'health': '/api/health',
            'trending': '/api/trending?limit=20',
            'search': '/api/search?q=spiderman',
            'details': '/api/details?url=<movie_url>'
        }
    })


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'message': '✅ API running in debug mode!'
    })


@app.route('/api/trending', methods=['GET'])
def get_trending():
    try:
        limit = request.args.get('limit', 20, type=int)
        results = get_scraper().scrape_home(limit=limit)
        return jsonify({
            'success': True,
            'count': len(results),
            'data': results
        })
    except Exception as e:
        logger.error(f"❌ Trending error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/search', methods=['GET'])
def search():
    try:
        keyword = request.args.get('q', '').strip()
        
        if not keyword:
            return jsonify({
                'success': False,
                'error': 'Give me something to search bro! 🔍'
            }), 400
        
        limit = request.args.get('limit', 20, type=int)
        results = get_scraper().search(keyword, limit=limit)
        
        return jsonify({
            'success': True,
            'keyword': keyword,
            'count': len(results),
            'data': results
        })
    except Exception as e:
        logger.error(f"❌ Search error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/details', methods=['GET'])
def get_details():
    try:
        url = request.args.get('url', '').strip()
        
        if not url:
            return jsonify({
                'success': False,
                'error': 'Need a movie URL bro! 🎬'
            }), 400
        
        details = get_scraper().get_details_with_servers(url)
        
        return jsonify({
            'success': True,
            'data': details
        })
    except Exception as e:
        logger.error(f"❌ Details error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("=" * 60)
    print("🎬 FlixHQ API v3.1 - DEBUG MODE")
    print("=" * 60)
    print("\n📡 Endpoints:")
    print("  GET /")
    print("  GET /api/health")
    print("  GET /api/trending?limit=20")
    print("  GET /api/search?q=keyword")
    print("  GET /api/details?url=<movie_url>")
    print("\n🔍 Will show ALL button texts and data-ids!")
    
    port = int(os.getenv('PORT', 8080))
    print(f"\n🚀 Starting on port {port}")
    print("=" * 60)
    
    try:
        app.run(debug=False, host='0.0.0.0', port=port)
    except KeyboardInterrupt:
        print("\n👋 Shutting down!")
        if scraper:
            scraper.close()
