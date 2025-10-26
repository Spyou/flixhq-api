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
from webdriver_manager.chrome import ChromeDriverManager
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
                break
        
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
        
        user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
        ]
        chrome_options.add_argument(f'user-agent={random.choice(user_agents)}')
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        self.driver.set_page_load_timeout(30)
        logger.info("✓ Chrome initialized")
    
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
        """Get TMDB ID for VidSrc"""
        try:
            clean_title = self.clean_title(title)
            api_key = os.getenv('TMDB_API_KEY', '8d6d91941230817f7807d643736e8a49')
            
            params = {
                'api_key': api_key,
                'query': clean_title,
                'year': year
            }
            
            response = requests.get('https://api.themoviedb.org/3/search/movie', params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    tmdb_id = data['results'][0]['id']
                    logger.info(f"✓ TMDB ID: {tmdb_id}")
                    return tmdb_id
        except Exception as e:
            logger.warning(f"TMDB lookup failed: {e}")
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
            # EXTRACT FLIXHQ UPCLOUD & VIDCLOUD SERVERS 🔥
            # ============================================================
            
            stream_servers = []
            
            try:
                logger.info("Looking for UpCloud and VidCloud servers...")
                
                # Find all server selection elements
                server_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    'a.btn, button.btn, div[data-id], a[data-id], a[data-linkid], .server-item, .server-name, [class*="server"]')
                
                logger.info(f"Found {len(server_elements)} potential server elements")
                
                for element in server_elements:
                    try:
                        # Get server name/text
                        server_text = element.text.strip().lower()
                        
                        # Check if it's UpCloud or VidCloud
                        if 'upcloud' in server_text or 'vidcloud' in server_text or 'megacloud' in server_text:
                            logger.info(f"Found server: {server_text}")
                            
                            # Try to click the server button
                            try:
                                element.click()
                                time.sleep(2)  # Wait for iframe to load
                                
                                # Get the new page source
                                new_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                                
                                # Find iframe
                                iframe = new_soup.find('iframe', id=lambda x: x and 'iframe' in str(x).lower())
                                if not iframe:
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
                                        
                                        logger.info(f"✓ Extracted {server_name}: {iframe_src[:50]}...")
                                
                            except Exception as click_error:
                                logger.warning(f"Could not click server button: {click_error}")
                    
                    except Exception as element_error:
                        continue
                
                # Alternative method: Look for data attributes
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Find UpCloud/VidCloud/MegaCloud links
                for server_name in ['upcloud', 'vidcloud', 'megacloud']:
                    elements = soup.find_all(lambda tag: tag.name in ['a', 'button', 'div'] and 
                                             (server_name in str(tag.get('class', '')).lower() or 
                                              server_name in tag.get_text().lower()))
                    
                    for elem in elements:
                        data_id = elem.get('data-id') or elem.get('data-linkid') or elem.get('href')
                        if data_id:
                            stream_servers.append({
                                'server': server_name.title(),
                                'url': data_id,
                                'type': 'link_id'
                            })
                
            except Exception as server_error:
                logger.error(f"Error extracting servers: {server_error}")
            
            # ============================================================
            # ADD VIDSRC STREAMS 🎯
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
            
            logger.info(f"🎉 Total: {len(unique_servers)} servers (FlixHQ + VidSrc)")
            
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
        'version': '10.0.0',
        'message': '🎬 FlixHQ (UpCloud/VidCloud/MegaCloud) + VidSrc!',
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
        'message': '✅ FlixHQ + VidSrc API running'
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
    """
    Get movie details with FlixHQ + VidSrc servers
    
    Example:
        GET /api/details?url=https://flixhq-tv.lol/movie/watch-avengers-2012
    """
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
    print("🎬 FlixHQ + VidSrc API v10.0")
    print("=" * 60)
    print("\n✅ FlixHQ: UpCloud, VidCloud, MegaCloud")
    print("✅ VidSrc.to, VidSrc.pro, VidSrc.xyz")
    print("\nEndpoints:")
    print("  GET /api/health")
    print("  GET /api/trending?limit=20")
    print("  GET /api/search?q=keyword")
    print("  GET /api/details?url=<movie_url>")
    
    port = int(os.getenv('PORT', 8080))
    print(f"\n🚀 Starting on port {port}")
    print("=" * 60)
    
    try:
        app.run(debug=False, host='0.0.0.0', port=port)
    except KeyboardInterrupt:
        print("\nShutting down...")
        if scraper:
            scraper.close()
