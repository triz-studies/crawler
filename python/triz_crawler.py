#!/usr/bin/env python3
"""
TRIZ Knowledge Base Web Crawler
Recursively crawls all content and images from the TRIZ wiki
"""

import requests
from bs4 import BeautifulSoup
import urllib.parse
import os
import time
import json
from urllib.robotparser import RobotFileParser
import hashlib
from pathlib import Path
import re
from typing import Set, Dict, List, Optional
import logging

# Configuration parameters
BASE_URL = "https://wiki.matriz.org"
START_URL = "https://wiki.matriz.org/knowledge-base/triz/"
OUTPUT_DIR = "triz_content"
MAX_DEPTH = 5
DELAY_BETWEEN_REQUESTS = 1  # seconds
MAX_RETRIES = 3
TIMEOUT = 30
BYPASS_ROBOTS = True  # Set to True to bypass robots.txt restrictions

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TRIZCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.visited_urls: Set[str] = set()
        self.url_content_map: Dict[str, Dict] = {}
        self.image_urls: Set[str] = set()
        self.robots_parser = RobotFileParser()
        self.robots_parser.set_url(f"{BASE_URL}/robots.txt")
        
        # Create output directories
        self.setup_directories()
        
    def setup_directories(self):
        """Create necessary output directories"""
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
        Path(f"{OUTPUT_DIR}/html").mkdir(exist_ok=True)
        Path(f"{OUTPUT_DIR}/images").mkdir(exist_ok=True)
        Path(f"{OUTPUT_DIR}/data").mkdir(exist_ok=True)
        
    def is_allowed_by_robots(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        if BYPASS_ROBOTS:
            return True
            
        try:
            return self.robots_parser.can_fetch(self.session.headers['User-Agent'], url)
        except Exception as e:
            logger.warning(f"Robots.txt check failed: {e}")
            return True  # Default to allowed if robots.txt fails
            
    def normalize_url(self, url: str, base_url: str) -> str:
        """Normalize URL to absolute form"""
        if url.startswith('#'):
            return base_url
        if url.startswith('javascript:'):
            return base_url
        if url.startswith('mailto:'):
            return base_url
            
        try:
            parsed = urllib.parse.urljoin(base_url, url)
            # Remove fragments
            parsed = urllib.parse.urlparse(parsed)
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))
        except:
            return base_url
            
    def is_valid_triz_url(self, url: str) -> bool:
        """Check if URL is part of the TRIZ knowledge base"""
        return (url.startswith(BASE_URL) and 
                '/knowledge-base/triz/' in url and
                not url.endswith(('.pdf', '.zip', '.doc', '.docx')) and
                '#' not in url)
                
    def extract_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """Extract all valid links from the page"""
        links = set()
        
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            normalized_url = self.normalize_url(href, base_url)
            
            if self.is_valid_triz_url(normalized_url):
                links.add(normalized_url)
                
        return links
        
    def extract_images(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """Extract all image URLs from the page"""
        images = set()
        
        for img in soup.find_all('img'):
            src = img.get('src')
            if src:
                normalized_url = self.normalize_url(src, base_url)
                if normalized_url.startswith(BASE_URL):
                    images.add(normalized_url)
                    
        return images
        
    def extract_text_content(self, soup: BeautifulSoup) -> Dict:
        """Extract structured text content from the page"""
        content = {
            'title': '',
            'headings': [],
            'paragraphs': [],
            'lists': [],
            'tables': [],
            'metadata': {}
        }
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            content['title'] = title_tag.get_text(strip=True)
            
        # Extract headings
        for i in range(1, 7):
            for heading in soup.find_all(f'h{i}'):
                content['headings'].append({
                    'level': i,
                    'text': heading.get_text(strip=True),
                    'id': heading.get('id', '')
                })
                
        # Extract paragraphs
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if text:
                content['paragraphs'].append(text)
                
        # Extract lists
        for ul in soup.find_all(['ul', 'ol']):
            list_items = []
            for li in ul.find_all('li'):
                list_items.append(li.get_text(strip=True))
            if list_items:
                content['lists'].append({
                    'type': ul.name,
                    'items': list_items
                })
                
        # Extract tables
        for table in soup.find_all('table'):
            table_data = []
            for row in table.find_all('tr'):
                row_data = []
                for cell in row.find_all(['td', 'th']):
                    row_data.append(cell.get_text(strip=True))
                if row_data:
                    table_data.append(row_data)
            if table_data:
                content['tables'].append(table_data)
                
        # Extract metadata
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            name = meta.get('name') or meta.get('property')
            content_attr = meta.get('content')
            if name and content_attr:
                content['metadata'][name] = content_attr
                
        return content
        
    def download_image(self, image_url: str) -> bool:
        """Download an image and save it locally"""
        try:
            response = self.session.get(image_url, timeout=TIMEOUT)
            if response.status_code == 200:
                # Create filename from URL
                filename = hashlib.md5(image_url.encode()).hexdigest()
                extension = self.get_image_extension(image_url, response.headers.get('content-type', ''))
                filename = f"{filename}{extension}"
                
                filepath = Path(f"{OUTPUT_DIR}/images/{filename}")
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                    
                logger.info(f"Downloaded image: {image_url} -> {filename}")
                return True
            else:
                logger.warning(f"Failed to download image {image_url}: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error downloading image {image_url}: {e}")
            return False
            
    def get_image_extension(self, url: str, content_type: str) -> str:
        """Determine image file extension"""
        # Try to get extension from URL
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.lower()
        
        if '.jpg' in path or '.jpeg' in path:
            return '.jpg'
        elif '.png' in path:
            return '.png'
        elif '.gif' in path:
            return '.gif'
        elif '.svg' in path:
            return '.svg'
        elif '.webp' in path:
            return '.webp'
            
        # Try to get from content type
        if 'jpeg' in content_type or 'jpg' in content_type:
            return '.jpg'
        elif 'png' in content_type:
            return '.png'
        elif 'gif' in content_type:
            return '.gif'
        elif 'svg' in content_type:
            return '.svg'
        elif 'webp' in content_type:
            return '.webp'
            
        return '.jpg'  # Default
        
    def crawl_page(self, url: str, depth: int = 0) -> Optional[Dict]:
        """Crawl a single page and extract all content"""
        if depth > MAX_DEPTH or url in self.visited_urls:
            return None
            
        if not self.is_allowed_by_robots(url):
            logger.info(f"Skipping {url} (not allowed by robots.txt)")
            return None
            
        logger.info(f"Crawling {url} (depth: {depth})")
        
        try:
            response = self.session.get(url, timeout=TIMEOUT)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch {url}: {response.status_code}")
                return None
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract content
            content = self.extract_text_content(soup)
            links = self.extract_links(soup, url)
            images = self.extract_images(soup, url)
            
            # Download images
            for image_url in images:
                if image_url not in self.image_urls:
                    self.download_image(image_url)
                    self.image_urls.add(image_url)
                    
            # Save HTML content
            html_filename = hashlib.md5(url.encode()).hexdigest() + '.html'
            html_filepath = Path(f"{OUTPUT_DIR}/html/{html_filename}")
            with open(html_filepath, 'w', encoding='utf-8') as f:
                f.write(str(soup))
                
            # Create page data
            page_data = {
                'url': url,
                'depth': depth,
                'title': content['title'],
                'content': content,
                'links': list(links),
                'images': list(images),
                'html_file': html_filename,
                'timestamp': time.time()
            }
            
            self.url_content_map[url] = page_data
            self.visited_urls.add(url)
            
            # Save individual page data
            page_filename = f"{OUTPUT_DIR}/data/{html_filename.replace('.html', '.json')}"
            with open(page_filename, 'w', encoding='utf-8') as f:
                json.dump(page_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Successfully crawled {url}")
            return page_data
            
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return None
            
    def crawl_recursively(self, start_url: str):
        """Recursively crawl all pages starting from the given URL"""
        to_visit = [(start_url, 0)]
        
        while to_visit:
            current_url, depth = to_visit.pop(0)
            
            if current_url in self.visited_urls:
                continue
                
            page_data = self.crawl_page(current_url, depth)
            if page_data:
                # Add new links to visit
                for link in page_data['links']:
                    if link not in self.visited_urls:
                        to_visit.append((link, depth + 1))
                        
            # Respect rate limiting
            time.sleep(DELAY_BETWEEN_REQUESTS)
            
    def save_summary(self):
        """Save a summary of all crawled content"""
        summary = {
            'total_pages': len(self.url_content_map),
            'total_images': len(self.image_urls),
            'crawl_timestamp': time.time(),
            'base_url': BASE_URL,
            'start_url': START_URL,
            'pages': list(self.url_content_map.values())
        }
        
        summary_file = f"{OUTPUT_DIR}/crawl_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Summary saved to {summary_file}")
        
    def generate_sitemap(self):
        """Generate an HTML sitemap"""
        sitemap_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TRIZ Knowledge Base - Crawled Content</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .page {{ margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }}
        .title {{ font-weight: bold; color: #333; }}
        .url {{ color: #666; font-size: 0.9em; }}
        .content {{ margin-top: 10px; }}
        .stats {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>TRIZ Knowledge Base - Crawled Content</h1>
    
    <div class="stats">
        <h2>Statistics</h2>
        <p><strong>Total Pages:</strong> {len(self.url_content_map)}</p>
        <p><strong>Total Images:</strong> {len(self.image_urls)}</p>
        <p><strong>Crawl Date:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <h2>Pages</h2>
"""
        
        for url, data in self.url_content_map.items():
            sitemap_html += f"""
    <div class="page">
        <div class="title">{data['title']}</div>
        <div class="url">{data['url']}</div>
        <div class="content">
            <p><strong>Depth:</strong> {data['depth']}</p>
            <p><strong>Links:</strong> {len(data['links'])}</p>
            <p><strong>Images:</strong> {len(data['images'])}</p>
            <p><strong>HTML File:</strong> {data['html_file']}</p>
        </div>
    </div>
"""
            
        sitemap_html += """
</body>
</html>
"""
        
        sitemap_file = f"{OUTPUT_DIR}/sitemap.html"
        with open(sitemap_file, 'w', encoding='utf-8') as f:
            f.write(sitemap_html)
            
        logger.info(f"Sitemap saved to {sitemap_file}")

    def rewrite_links_to_offline(self, soup: BeautifulSoup, base_url: str) -> BeautifulSoup:
        """Rewrite all internal links to point to local HTML files"""
        # Create a copy to avoid modifying the original
        soup_copy = soup.copy()
        
        # Rewrite all anchor links
        for link in soup_copy.find_all('a', href=True):
            href = link.get('href')
            if href:
                normalized_url = self.normalize_url(href, base_url)
                
                if self.is_valid_triz_url(normalized_url):
                    # Check if we have a local file for this URL
                    local_filename = self.get_filename_for_url(normalized_url)
                    if local_filename:
                        # Rewrite to local file
                        link['href'] = local_filename
                        logger.debug(f"Rewrote link {href} -> {local_filename}")
                    else:
                        # If we don't have this page, remove the link or make it non-functional
                        link['href'] = '#'
                        link['title'] = f"Page not available offline: {normalized_url}"
                        link['style'] = 'color: #999; text-decoration: line-through;'
                        logger.debug(f"Disabled link {href} (not available offline)")
                elif href.startswith(BASE_URL):
                    # External link - keep as is but add target="_blank"
                    link['target'] = '_blank'
                    link['rel'] = 'noopener noreferrer'
        
        # Rewrite image sources to local files
        for img in soup_copy.find_all('img'):
            src = img.get('src')
            if src:
                normalized_url = self.normalize_url(src, base_url)
                if normalized_url.startswith(BASE_URL):
                    # Check if we have this image locally
                    if normalized_url in self.image_urls:
                        # Find the local image filename
                        try:
                            for local_img in os.listdir(f"{OUTPUT_DIR}/images"):
                                if local_img.startswith(hashlib.md5(normalized_url.encode()).hexdigest()):
                                    img['src'] = f"../images/{local_img}"
                                    logger.debug(f"Rewrote image {src} -> ../images/{local_img}")
                                    break
                        except Exception as e:
                            logger.warning(f"Error processing image {src}: {e}")
                    else:
                        # Image not available offline
                        img['src'] = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlIG5vdCBhdmFpbGFibGUgb2ZmbGluZTwvdGV4dD48L3N2Zz4="
                        img['alt'] = "Image not available offline"
                        logger.debug(f"Replaced offline image {src} with placeholder")
        
        return soup_copy

def main():
    """Main function to run the crawler"""
    logger.info("Starting TRIZ Knowledge Base crawler...")
    logger.info(f"Bypassing robots.txt: {BYPASS_ROBOTS}")
    
    try:
        crawler = TRIZCrawler()
        crawler.crawl_recursively(START_URL)
        
        # Save results
        crawler.save_summary()
        crawler.generate_sitemap()
        
        logger.info("Crawling completed successfully!")
        logger.info(f"Total pages crawled: {len(crawler.url_content_map)}")
        logger.info(f"Total images downloaded: {len(crawler.image_urls)}")
        
    except KeyboardInterrupt:
        logger.info("Crawling interrupted by user")
    except Exception as e:
        logger.error(f"Crawling failed: {e}")

if __name__ == "__main__":
    main()
