#!/usr/bin/env python3
"""
FlixHQ API - Extract UpCloud & VidCloud Streaming Links
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import random
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


class FlixHQAPI:
    """FlixHQ scraper with UpCloud/VidCloud extraction"""
    
    def __init__(self):
        """Initialize Chrome"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        
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
    
    def scrape_home(self, limit=20):
        """Get trending movies"""
        try:
            url = "https://flixhq-tv.lol/home"
            self.driver.get(url)
            time.sleep(random.uniform(2, 3))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = self._extract_items(soup)
            
            return items[:limit] if limit else items
        except Exception as e:
            logger.error(f"Error scraping home: {e}")
            return []
    
    def search(self, keyword, limit=20):
        """Search movies"""
        try:
            search_url = f"https://flixhq-tv.lol/search/{keyword.replace(' ', '-')}"
            self.driver.get(search_url)
            time.sleep(random.uniform(2, 3))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = self._extract_items(soup)
            
            return items[:limit] if limit else items
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return []
    
    def get_details_with_servers(self, movie_url):
        """
        Get movie details + UpCloud/VidCloud servers
        """
        try:
            logger.info(f"Getting details for: {movie_url}")
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
        
            
            stream_servers = []
            
            try:
                # Look for server buttons/links
                logger.info("Looking for UpCloud and VidCloud servers...")
                
                # Find all server selection elements
                server_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    'a.btn, button.btn, div[data-id], a[data-id], a[data-linkid], .server-item, .server-name, [class*="server"]')
                
                logger.info(f"Found {len(server_elements)} potential server elements")
                
                for element in server_elements:
                    try:
                        server_text = element.text.strip().lower()
                        
                        # Check UpCloud or VidCloud
                        if 'upcloud' in server_text or 'vidcloud' in server_text:
                            logger.info(f"Found server: {server_text}")
                            
                            # Click the server button
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
                                logger.warning(f"Could not click server button: {click_error}")
                    
                    except Exception as element_error:
                        continue
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # UpCloud links
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
                
                # Find VidCloud links
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
            
            logger.info(f"✓ Found {len(unique_servers)} servers (UpCloud/VidCloud)")
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting details: {e}")
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
scraper = FlixHQAPI()

# Api Endpoints

@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'message': 'FlixHQ API (UpCloud/VidCloud) is running'
    })


@app.route('/api/trending', methods=['GET'])
def get_trending():
    """Get trending movies"""
    try:
        limit = request.args.get('limit', 20, type=int)
        results = scraper.scrape_home(limit=limit)
        
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
        results = scraper.search(keyword, limit=limit)
        
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
    Get movie details with UpCloud/VidCloud servers only
    
    Example:
        GET /api/details?url=https://flixhq-tv.lol/movie/watch-our-fault-movies-free-135628
    """
    try:
        url = request.args.get('url', '').strip()
        
        if not url:
            return jsonify({
                'success': False,
                'error': 'Missing movie URL'
            }), 400
        
        details = scraper.get_details_with_servers(url)
        
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
    print("FlixHQ API - UpCloud & VidCloud Only")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET /api/health")
    print("  GET /api/trending?limit=20")
    print("  GET /api/search?q=keyword")
    print("  GET /api/details?url=<movie_url>")
    print("\nStarting on http://localhost:5000")
    print("=" * 60)
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\nShutting down...")
        scraper.close()
