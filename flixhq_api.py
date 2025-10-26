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
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


class MovieAPI:
    
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
            logger.info("✓ Chrome ready! 🎬")
        except Exception as e1:
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.set_page_load_timeout(30)
            except Exception as e2:
                logger.error(f"Chrome failed: {e2}")
                sys.exit(1)
    
    def scrape_home(self, limit=20):
        """Scrape FlixHQ homepage"""
        try:
            self.driver.get("https://flixhq-tv.lol/home")
            time.sleep(3)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = self._extract_items(soup)
            logger.info(f"✓ Found {len(items)} movies!")
            return items[:limit]
        except Exception as e:
            logger.error(f"Home failed: {e}")
            return []
    
    def search(self, keyword, limit=20):
        """Search FlixHQ"""
        try:
            search_url = f"https://flixhq-tv.lol/search/{keyword.replace(' ', '-')}"
            logger.info(f"🔍 Searching: {keyword}")
            self.driver.get(search_url)
            time.sleep(3)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = self._extract_items(soup)
            logger.info(f"✓ Found {len(items)} results!")
            return items[:limit]
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def get_vidsrc_streams(self, tmdb_id=None, title=None, year=None):
        """Get VidSrc embed URLs (no encryption!)"""
        streams = []
        
        try:
            if tmdb_id:
                # VidSrc.to with TMDB ID
                vidsrc_url = f"https://vidsrc.to/embed/movie/{tmdb_id}"
                streams.append({
                    'server': 'VidSrc.to',
                    'url': vidsrc_url,
                    'type': 'embed'
                })
                logger.info(f"✓ Built VidSrc.to URL")
            
            if title:
                # VidSrc.pro with title
                clean_title = title.replace(' ', '-').lower()
                clean_title = re.sub(r'[^a-z0-9-]', '', clean_title)
                
                if year:
                    vidsrc_pro_url = f"https://vidsrc.pro/embed/movie/{clean_title}-{year}"
                else:
                    vidsrc_pro_url = f"https://vidsrc.pro/embed/movie/{clean_title}"
                
                streams.append({
                    'server': 'VidSrc.pro',
                    'url': vidsrc_pro_url,
                    'type': 'embed'
                })
                logger.info(f"✓ Built VidSrc.pro URL")
            
            # VidSrc.xyz backup
            if tmdb_id:
                vidsrc_xyz_url = f"https://vidsrc.xyz/embed/movie?tmdb={tmdb_id}"
                streams.append({
                    'server': 'VidSrc.xyz',
                    'url': vidsrc_xyz_url,
                    'type': 'embed'
                })
                logger.info(f"✓ Built VidSrc.xyz URL")
        
        except Exception as e:
            logger.error(f"VidSrc generation failed: {e}")
        
        return streams
    
    def get_tmdb_id(self, title, year=None):
        """Get TMDB ID from title (uses TMDB API)"""
        try:
            api_key = os.getenv('TMDB_API_KEY', 'YOUR_TMDB_API_KEY')  # Get free key from themoviedb.org
            
            search_url = f"https://api.themoviedb.org/3/search/movie"
            params = {
                'api_key': api_key,
                'query': title,
                'year': year
            }
            
            response = requests.get(search_url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    tmdb_id = data['results'][0]['id']
                    logger.info(f"✓ Found TMDB ID: {tmdb_id}")
                    return tmdb_id
        except Exception as e:
            logger.warning(f"TMDB lookup failed: {e}")
        
        return None
    
    def get_details_with_servers(self, movie_url):
        """Get movie details + FlixHQ + VidSrc streams"""
        try:
            logger.info(f"📽️ Getting details...")
            self.driver.get(movie_url)
            time.sleep(6)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            details = self._extract_basic_details(soup)
            
            # Extract title for VidSrc
            title_elem = soup.find('h1') or soup.find('h2', class_=lambda x: x and 'title' in str(x).lower())
            movie_title = title_elem.get_text(strip=True) if title_elem else None
            
            logger.info(f"🎬 Movie: {movie_title}")
            
            stream_sources = []
            
            # 1. Try FlixHQ servers
            logger.info("🎥 Looking for FlixHQ servers...")
            flixhq_servers = self._extract_flixhq_servers()
            stream_sources.extend(flixhq_servers)
            
            # 2. Add VidSrc streams
            logger.info("🎥 Adding VidSrc streams...")
            
            # Try to get TMDB ID
            tmdb_id = self.get_tmdb_id(movie_title, details.get('year'))
            
            vidsrc_streams = self.get_vidsrc_streams(
                tmdb_id=tmdb_id,
                title=movie_title,
                year=details.get('year')
            )
            stream_sources.extend(vidsrc_streams)
            
            details['servers'] = stream_sources
            details['server_count'] = len(stream_sources)
            
            logger.info(f"🎉 Total: {len(stream_sources)} servers")
            
            return details
            
        except Exception as e:
            logger.error(f"❌ Failed: {e}")
            return {
                'description': None,
                'year': None,
                'rating': None,
                'servers': [],
                'server_count': 0
            }
    
    def _extract_flixhq_servers(self):
        """Extract FlixHQ iframe servers"""
        servers = []
        
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            server_selectors = [
                '.server-list [data-id]',
                '.servers [data-id]',
                '[class*="server"] [data-id]',
                'ul[class*="server"] li[data-id]',
            ]
            
            server_buttons = []
            for selector in server_selectors:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if buttons:
                        logger.info(f"✓ Found {len(buttons)} buttons: {selector}")
                        server_buttons = buttons
                        break
                except:
                    continue
            
            if not server_buttons:
                all_buttons = self.driver.find_elements(By.CSS_SELECTOR, '[data-id]')
                server_buttons = [btn for btn in all_buttons if btn.get_attribute('data-id').isdigit() and len(btn.get_attribute('data-id')) > 3]
            
            for idx, button in enumerate(server_buttons[:3]):  # Limit to 3 servers
                try:
                    button_text = button.text.strip().lower()
                    data_id = button.get_attribute('data-id')
                    
                    if 'home' in button_text or 'movies' in button_text:
                        continue
                    
                    server_name = 'Server ' + data_id[-4:]
                    
                    if 'upcloud' in button_text:
                        server_name = 'UpCloud'
                    elif 'vidcloud' in button_text or 'akcloud' in button_text:
                        server_name = 'VidCloud'
                    elif 'megacloud' in button_text:
                        server_name = 'MegaCloud'
                    
                    self.driver.execute_script("arguments[0].click();", button)
                    time.sleep(3)
                    
                    iframe_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    iframe = iframe_soup.find('iframe')
                    
                    if iframe:
                        iframe_src = iframe.get('src') or iframe.get('data-src')
                        if iframe_src:
                            if not iframe_src.startswith('http'):
                                iframe_src = f"https:{iframe_src}" if iframe_src.startswith('//') else iframe_src
                            
                            if 'upcloud' in iframe_src.lower():
                                server_name = 'UpCloud'
                            elif 'vidcloud' in iframe_src.lower():
                                server_name = 'VidCloud'
                            elif 'megacloud' in iframe_src.lower():
                                server_name = 'MegaCloud'
                            
                            servers.append({
                                'server': server_name,
                                'url': iframe_src,
                                'type': 'iframe'
                            })
                            
                            logger.info(f"✓ Got {server_name}!")
                
                except Exception as e:
                    continue
        
        except Exception as e:
            logger.warning(f"FlixHQ extraction failed: {e}")
        
        return servers
    
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


scraper = None

def get_scraper():
    global scraper
    if scraper is None:
        scraper = MovieAPI()
    return scraper


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'name': 'Movie Streaming API',
        'version': '7.0.0',
        'message': '🎬 FlixHQ + VidSrc Support!',
        'sources': ['FlixHQ (UpCloud, VidCloud, MegaCloud)', 'VidSrc.to', 'VidSrc.pro', 'VidSrc.xyz'],
        'endpoints': {
            'health': '/api/health',
            'trending': '/api/trending?limit=20',
            'search': '/api/search?q=keyword',
            'details': '/api/details?url=<movie_url>'
        },
        'note': 'VidSrc streams work without encryption! 🎉'
    })


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'message': '✅ API running!'})


@app.route('/api/trending', methods=['GET'])
def get_trending():
    try:
        limit = request.args.get('limit', 20, type=int)
        results = get_scraper().scrape_home(limit=limit)
        return jsonify({'success': True, 'count': len(results), 'data': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/search', methods=['GET'])
def search():
    try:
        keyword = request.args.get('q', '').strip()
        if not keyword:
            return jsonify({'success': False, 'error': 'Need keyword'}), 400
        limit = request.args.get('limit', 20, type=int)
        results = get_scraper().search(keyword, limit=limit)
        return jsonify({'success': True, 'keyword': keyword, 'count': len(results), 'data': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/details', methods=['GET'])
def get_details():
    try:
        url = request.args.get('url', '').strip()
        if not url:
            return jsonify({'success': False, 'error': 'Need URL'}), 400
        details = get_scraper().get_details_with_servers(url)
        return jsonify({'success': True, 'data': details})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("🎬 Movie Streaming API v7.0")
    print("=" * 60)
    print("\n✅ FlixHQ servers (if available)")
    print("✅ VidSrc.to, VidSrc.pro, VidSrc.xyz (always work!)")
    print("\n📡 Endpoints:")
    print("  GET /api/health")
    print("  GET /api/trending?limit=20")
    print("  GET /api/search?q=keyword")
    print("  GET /api/details?url=<movie_url>")
    
    port = int(os.getenv('PORT', 8080))
    print(f"\n🚀 Starting on port {port}\n")
    
    try:
        app.run(debug=False, host='0.0.0.0', port=port)
    except KeyboardInterrupt:
        if scraper:
            scraper.close()
