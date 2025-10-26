#!/usr/bin/env python3

from flask import Flask, jsonify, request
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
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
    """Scraper for FlixHQ with UpCloud/VidCloud extraction"""
    
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-setuid-sandbox')
        
        # Detect Chrome/Chromium binary
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
            logger.info(f"✓ Using Chrome binary: {chrome_binary}")
        else:
            logger.info("Chrome binary not found, using default system Chrome")
        
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
            logger.info("✓ Chrome initialized with ChromeDriverManager")
        except Exception as e1:
            logger.warning(f"ChromeDriverManager failed: {e1}")
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.set_page_load_timeout(30)
                logger.info("✓ Chrome initialized with system chromedriver")
            except Exception as e2:
                logger.error(f"All Chrome initialization failed: {e2}")
                sys.exit(1)
    
    def scrape_home(self, limit=20):
        """Get trending movies from home page"""
        try:
            url = "https://flixhq-tv.lol/home"
            logger.info(f"Scraping home page: {url}")
            self.driver.get(url)
            time.sleep(random.uniform(2, 3))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = self._extract_items(soup)
            
            logger.info(f"✓ Found {len(items)} items on home page")
            return items[:limit] if limit else items
        except Exception as e:
            logger.error(f"Error scraping home: {e}")
            return []
    
    def search(self, keyword, limit=20):
        """Search movies by keyword"""
        try:
            search_url = f"https://flixhq-tv.lol/search/{keyword.replace(' ', '-')}"
            logger.info(f"Searching for: {keyword}")
            self.driver.get(search_url)
            time.sleep(random.uniform(2, 3))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = self._extract_items(soup)
            
            logger.info(f"✓ Found {len(items)} results for '{keyword}'")
            return items[:limit] if limit else items
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return []
    
    def get_details_with_servers(self, movie_url):
        """Get movie details and streaming servers"""
        try:
            logger.info(f"Getting details for: {movie_url}")
            self.driver.get(movie_url)
            time.sleep(3)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
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
            
            stream_servers = []
            
            try:
                logger.info("Looking for UpCloud and VidCloud servers...")
                
                server_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    'a.btn, button.btn, div[data-id], a[data-id], a[data-linkid], .server-item, .server-name, [class*="server"]')
                
                logger.info(f"Found {len(server_elements)} potential servers")
                
                for element in server_elements:
                    try:
                        server_text = element.text.strip().lower()
                        if 'upcloud' in server_text or 'vidcloud' in server_text:
                            logger.info(f"Found server: {server_text}")
                            try:
                                element.click()
                                time.sleep(2)
                                new_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                                iframe = new_soup.find('iframe', id=lambda x: x and 'iframe' in str(x).lower())
                                if not iframe:
                                    iframe = new_soup.find('iframe')
                                
                                if iframe:
                                    iframe_src = iframe.get('src') or iframe.get('data-src')
                                    if iframe_src:
                                        if not iframe_src.startswith('http'):
                                            iframe_src = f"https:{iframe_src}" if iframe_src.startswith('//') else f"https://flixhq-tv.lol{iframe_src}"
                                        
                                        server_name = 'UpCloud' if 'upcloud' in server_text else 'VidCloud'
                                        stream_servers.append({
                                            'server': server_name,
                                            'url': iframe_src,
                                            'type': 'iframe'
                                        })
                                        logger.info(f"✓ Extracted {server_name}: {iframe_src[:50]}...")
                            except Exception as click_error:
                                logger.warning(f"Could not click server: {click_error}")
                    except Exception:
                        continue
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                upcloud_elements = soup.find_all(lambda tag: tag.name in ['a', 'button', 'div'] and 
                                                 ('upcloud' in str(tag.get('class', '')).lower() or 
                                                  'upcloud' in tag.get_text().lower()))
                for elem in upcloud_elements:
                    data_id = elem.get('data-id') or elem.get('data-linkid') or elem.get('href')
                    if data_id:
                        stream_servers.append({
                            'server': 'UpCloud',
                            'url': data_id,
                            'type': 'link_id'
                        })
                
                vidcloud_elements = soup.find_all(lambda tag: tag.name in ['a', 'button', 'div'] and 
                                                  ('vidcloud' in str(tag.get('class', '')).lower() or 
                                                   'vidcloud' in tag.get_text().lower()))
                for elem in vidcloud_elements:
                    data_id = elem.get('data-id') or elem.get('data-linkid') or elem.get('href')
                    if data_id:
                        stream_servers.append({
                            'server': 'VidCloud',
                            'url': data_id,
                            'type': 'link_id'
                        })
                
            except Exception as server_error:
                logger.error(f"Error extracting servers: {server_error}")
            
            unique_servers = []
            seen_urls = set()
            for server in stream_servers:
                if server['url'] not in seen_urls:
                    seen_urls.add(server['url'])
                    unique_servers.append(server)
            
            details['servers'] = unique_servers
            details['server_count'] = len(unique_servers)
            
            logger.info(f"✓ Found {len(unique_servers)} servers")
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting details: {e}")
            return {}
    
    def _extract_items(self, soup):
        """Extract movie or TV items"""
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
        """Parse single movie/TV item"""
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
        """Close the Chrome driver"""
        if self.driver:
            self.driver.quit()
            logger.info("✓ Chrome driver closed")


scraper = None

def get_scraper():
    """Get or create scraper instance"""
    global scraper
    if scraper is None:
        scraper = FlixHQAPI()
    return scraper


@app.route('/', methods=['GET'])
def home():
    """API home info"""
    return jsonify({
        'name': 'FlixHQ API',
        'version': '1.0.0',
        'endpoints': {
            'health': '/api/health',
            'trending': '/api/trending?limit=20',
            'search': '/api/search?q=keyword&limit=20',
            'details': '/api/details?url=<movie_url>'
        }
    })


@app.route('/api/health', methods=['GET'])
def health():
    """Check API health"""
    return jsonify({
        'status': 'ok',
        'message': 'FlixHQ API is running'
    })


@app.route('/api/trending', methods=['GET'])
def get_trending():
    """Return trending movies"""
    try:
        limit = request.args.get('limit', 20, type=int)
        results = get_scraper().scrape_home(limit=limit)
        return jsonify({'success': True, 'count': len(results), 'data': results})
    except Exception as e:
        logger.error(f"Error in /api/trending: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/search', methods=['GET'])
def search():
    """Search movies by query"""
    try:
        keyword = request.args.get('q', '').strip()
        if not keyword:
            return jsonify({'success': False, 'error': 'Missing search keyword'}), 400
        limit = request.args.get('limit', 20, type=int)
        results = get_scraper().search(keyword, limit=limit)
        return jsonify({'success': True, 'keyword': keyword, 'count': len(results), 'data': results})
    except Exception as e:
        logger.error(f"Error in /api/search: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/details', methods=['GET'])
def get_details():
    """Return movie details and streaming servers"""
    try:
        url = request.args.get('url', '').strip()
        if not url:
            return jsonify({'success': False, 'error': 'Missing movie URL'}), 400
        details = get_scraper().get_details_with_servers(url)
        return jsonify({'success': True, 'data': details})
    except Exception as e:
        logger.error(f"Error in /api/details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("FlixHQ API - UpCloud & VidCloud Only")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET /")
    print("  GET /api/health")
    print("  GET /api/trending?limit=20")
    print("  GET /api/search?q=keyword")
    print("  GET /api/details?url=<movie_url>")
    print("\nStarting on http://0.0.0.0:5000")
    print("=" * 60)
    
    try:
        port = int(os.getenv('PORT', 5000))
        app.run(debug=False, host='0.0.0.0', port=port)
    except KeyboardInterrupt:
        print("\nShutting down...")
        if scraper:
            scraper.close()
