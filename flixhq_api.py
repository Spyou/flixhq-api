#!/usr/bin/env python3
"""
FlixHQ + VidSrc API - Extract UpCloud, VidCloud & VidSrc
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
import random
import logging
import re
import os
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


class FlixHQAPI:
    """FlixHQ + VidSrc scraper"""
    
    def __init__(self):
        """Initialize Chrome"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-setuid-sandbox')
        
        # Chrome binary paths for deployment
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
                logger.info(f"Found Chrome at: {path}")
                break
        
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
        
        user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
        ]
        chrome_options.add_argument(f'user-agent={random.choice(user_agents)}')
        
        # Try to initialize Chrome
        try:
            # Try without webdriver-manager first (for Railway)
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)
            logger.info("✓ Chrome initialized (system chromedriver)")
        except Exception as e1:
            logger.warning(f"System chromedriver failed: {e1}")
            try:
                # Try with webdriver-manager (for local)
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.driver.set_page_load_timeout(30)
                logger.info("✓ Chrome initialized (webdriver-manager)")
            except Exception as e2:
                logger.error(f"Both methods failed: {e2}")
                raise
    
    def clean_title(self, title):
        """Clean movie title"""
        if not title:
            return None
        title = re.sub(r'\s*-?\s*(watch|free|hd|1080p|720p|online|movies?).*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*\(.*?\)\s*$', '', title)
        return title.strip()
    
    def scrape_home(self, limit=20):
        """Get trending movies"""
        try:
            url = "https://flixhq-tv.lol/home"
            logger.info(f"Scraping: {url}")
            self.driver.get(url)
            time.sleep(random.uniform(2, 3))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = self._extract_items(soup)
            
            logger.info(f"✓ Found {len(items)} movies")
            return items[:limit] if limit else items
        except Exception as e:
            logger.error(f"Error scraping home: {e}")
            return []
    
    def search(self, keyword, limit=20):
        """Search movies"""
        try:
            search_url = f"https://flixhq-tv.lol/search/{keyword.replace(' ', '-')}"
            logger.info(f"Searching: {search_url}")
            self.driver.get(search_url)
            time.sleep(random.uniform(2, 3))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = self._extract_items(soup)
            
            logger.info(f"✓ Found {len(items)} results")
            return items[:limit] if limit else items
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return []
    
    def get_tmdb_id(self, title, year=None):
        """Get TMDB ID using jumpfreedom.com (100% FREE, NO API KEY!)"""
        try:
            clean_title = self.clean_title(title)
            logger.info(f"🔍 Searching jumpfreedom.com: {clean_title}")
            
            # jumpfreedom.com = Free TMDB proxy
            search_url = "https://jumpfreedom.com/3/search/movie"
            params = {'query': clean_title}
            if year:
                params['year'] = year
            
            response = requests.get(search_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if results:
                    tmdb_id = results[0]['id']
                    logger.info(f"✓ Found TMDB ID: {tmdb_id}")
                    return tmdb_id
                else:
                    logger.warning(f"No results for: {clean_title}")
            else:
                logger.warning(f"API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"jumpfreedom.com failed: {e}")
        
        return None


    
    def get_vidsrc_streams(self, tmdb_id=None, title=None, year=None):
        """Generate VidSrc URLs"""
        streams = []
        
        if tmdb_id:
            streams.append({
                'server': 'VidSrc.to',
                'url': f"https://vidsrc.to/embed/movie/{tmdb_id}",
                'type': 'embed'
            })
            streams.append({
                'server': 'VidSrc.xyz',
                'url': f"https://vidsrc.xyz/embed/movie?tmdb={tmdb_id}",
                'type': 'embed'
            })
        
        if title:
            clean_title = self.clean_title(title)
            url_title = clean_title.replace(' ', '-').lower()
            url_title = re.sub(r'[^a-z0-9-]', '', url_title)
            
            if year:
                url = f"https://vidsrc.pro/embed/movie/{url_title}-{year}"
            else:
                url = f"https://vidsrc.pro/embed/movie/{url_title}"
            
            streams.append({
                'server': 'VidSrc.pro',
                'url': url,
                'type': 'embed'
            })
        
        return streams
    
    def get_details_with_servers(self, movie_url):
        """
        Get movie details + FlixHQ servers + VidSrc
        """
        try:
            logger.info(f"Getting: {movie_url}")
            self.driver.get(movie_url)
            time.sleep(3)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            details = {}
            
            # Extract description
            desc_elem = soup.find(class_=lambda x: x and 'description' in str(x).lower())
            if desc_elem:
                details['description'] = desc_elem.get_text(strip=True)[:500]
            else:
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                details['description'] = meta_desc.get('content', None) if meta_desc else None
            
            # Extract year
            year_elem = soup.find(class_=lambda x: x and 'year' in str(x).lower())
            if year_elem:
                year_match = re.search(r'\b(19\d{2}|20[0-3]\d)\b', year_elem.get_text())
                details['year'] = year_match.group(1) if year_match else None
            else:
                details['year'] = None
            
            # Extract rating
            rating_elem = soup.find(class_=lambda x: x and ('rating' in str(x).lower() or 'imdb' in str(x).lower()))
            if rating_elem:
                rating_match = re.search(r'(\d+\.?\d*)', rating_elem.get_text())
                details['rating'] = rating_match.group(1) if rating_match else None
            else:
                details['rating'] = None
            
            # Extract title
            title_elem = soup.find('h1') or soup.find('h2')
            if not title_elem:
                og_title = soup.find('meta', property='og:title')
                raw_title = og_title.get('content') if og_title else None
            else:
                raw_title = title_elem.get_text(strip=True)
            
            movie_title = self.clean_title(raw_title)
            details['clean_title'] = movie_title
            
            logger.info(f"🎬 Movie: {movie_title} ({details.get('year', 'N/A')})")
            
            # ============================================================
            # EXTRACT FLIXHQ SERVERS
            # ============================================================
            
            stream_servers = []
            
            try:
                logger.info("Looking for FlixHQ servers...")
                
                # Find all server selection elements
                server_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    'a.btn, button.btn, div[data-id], a[data-id], a[data-linkid], .server-item, .server-name, [class*="server"]')
                
                logger.info(f"Found {len(server_elements)} potential server elements")
                
                for element in server_elements:
                    try:
                        server_text = element.text.strip().lower()
                        
                        if 'upcloud' in server_text or 'vidcloud' in server_text or 'megacloud' in server_text:
                            logger.info(f"Found server: {server_text}")
                            
                            try:
                                element.click()
                                time.sleep(2)
                                
                                new_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                                iframe = new_soup.find('iframe')
                                
                                if iframe:
                                    iframe_src = iframe.get('src') or iframe.get('data-src')
                                    
                                    if iframe_src:
                                        if not iframe_src.startswith('http'):
                                            iframe_src = f"https:{iframe_src}" if iframe_src.startswith('//') else f"https://flixhq-tv.lol{iframe_src}"
                                        
                                        server_name = 'UpCloud' if 'upcloud' in server_text else 'VidCloud' if 'vidcloud' in server_text else 'MegaCloud'
                                        
                                        stream_servers.append({
                                            'server': server_name,
                                            'url': iframe_src,
                                            'type': 'iframe'
                                        })
                                        
                                        logger.info(f"✓ Extracted {server_name}")
                                
                            except Exception as click_error:
                                logger.warning(f"Click failed: {click_error}")
                    
                    except Exception as element_error:
                        continue
                
            except Exception as server_error:
                logger.error(f"Server extraction error: {server_error}")
            
            # ============================================================
            # ADD VIDSRC STREAMS
            # ============================================================
            
            logger.info("Adding VidSrc streams...")
            tmdb_id = self.get_tmdb_id(movie_title, details.get('year'))
            vidsrc_streams = self.get_vidsrc_streams(tmdb_id, movie_title, details.get('year'))
            stream_servers.extend(vidsrc_streams)
            
            # Remove duplicates
            unique_servers = []
            seen_urls = set()
            for server in stream_servers:
                if server['url'] not in seen_urls:
                    seen_urls.add(server['url'])
                    unique_servers.append(server)
            
            details['servers'] = unique_servers
            details['server_count'] = len(unique_servers)
            
            logger.info(f"🎉 Total: {len(unique_servers)} servers")
            
            return details
            
        except Exception as e:
            logger.error(f"Error: {e}")
            return {}
    
    def _extract_items(self, soup):
        """Extract movie items"""
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
        """Parse single item"""
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
            item['thumbnail'] = (
                img.get('data-src') or img.get('src') or None
            ) if img else None
            
            item['type'] = 'movie' if '/movie/' in item['link'] else 'tv' if '/tv/' in item['link'] else 'unknown'
            
            return item
        except:
            return None
    
    def close(self):
        """Close driver"""
        if self.driver:
            self.driver.quit()


# Initialize scraper
scraper = None

def get_scraper():
    global scraper
    if scraper is None:
        scraper = FlixHQAPI()
    return scraper


# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'name': 'FlixHQ + VidSrc API',
        'version': '10.1.0',
        'message': '🎬 FlixHQ + VidSrc (Railway Fixed)',
        'sources': ['FlixHQ: UpCloud, VidCloud, MegaCloud', 'VidSrc.to', 'VidSrc.pro', 'VidSrc.xyz'],
        'endpoints': {
            'health': '/api/health',
            'trending': '/api/trending?limit=20',
            'search': '/api/search?q=keyword',
            'details': '/api/details?url=<movie_url>'
        }
    })


@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'message': '✅ API running'
    })


@app.route('/api/trending', methods=['GET'])
def get_trending():
    """Get trending movies"""
    try:
        limit = request.args.get('limit', 20, type=int)
        results = get_scraper().scrape_home(limit=limit)
        
        return jsonify({
            'success': True,
            'count': len(results),
            'data': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/search', methods=['GET'])
def search():
    """Search movies"""
    try:
        keyword = request.args.get('q', '').strip()
        
        if not keyword:
            return jsonify({
                'success': False,
                'error': 'Missing search keyword'
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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/details', methods=['GET'])
def get_details():
    """Get movie details with servers"""
    try:
        url = request.args.get('url', '').strip()
        
        if not url:
            return jsonify({
                'success': False,
                'error': 'Missing movie URL'
            }), 400
        
        details = get_scraper().get_details_with_servers(url)
        
        return jsonify({
            'success': True,
            'data': details
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("=" * 60)
    print("🎬 FlixHQ + VidSrc API v10.1")
    print("=" * 60)
    
    port = int(os.getenv('PORT', 8080))
    print(f"\n🚀 Starting on port {port}")
    print("=" * 60)
    
    try:
        app.run(debug=False, host='0.0.0.0', port=port)
    except KeyboardInterrupt:
        print("\nShutting down...")
        if scraper:
            scraper.close()
