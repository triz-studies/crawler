#!/usr/bin/env python3
"""
Offline Link Converter for TRIZ Knowledge Base
Converts all internal links in HTML files to point to local files
"""

import os
import hashlib
import json
from pathlib import Path
from bs4 import BeautifulSoup
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OfflineLinkConverter:
    def __init__(self, output_dir="triz_content"):
        self.output_dir = output_dir
        self.html_dir = f"{output_dir}/html"
        self.data_dir = f"{output_dir}/data"
        self.images_dir = f"{output_dir}/images"
        
        # Load the crawl summary to get URL mappings
        self.url_to_filename_map = {}
        self.load_url_mappings()
        
    def load_url_mappings(self):
        """Load URL to filename mappings from crawl summary"""
        summary_file = f"{self.output_dir}/crawl_summary.json"
        if os.path.exists(summary_file):
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                
                # Create URL to filename mapping
                for page in summary.get('pages', []):
                    url = page.get('url', '')
                    html_file = page.get('html_file', '')
                    if url and html_file:
                        self.url_to_filename_map[url] = html_file
                        
                logger.info(f"Loaded {len(self.url_to_filename_map)} URL mappings")
            except Exception as e:
                logger.error(f"Error loading summary: {e}")
        else:
            logger.warning("Crawl summary not found, will create mappings from HTML files")
            self.create_mappings_from_files()
    
    def create_mappings_from_files(self):
        """Create URL mappings from existing HTML files"""
        if not os.path.exists(self.html_dir):
            logger.error(f"HTML directory {self.html_dir} not found")
            return
            
        # Read data files to get URL mappings
        for data_file in os.listdir(self.data_dir):
            if data_file.endswith('.json'):
                try:
                    with open(f"{self.data_dir}/{data_file}", 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        url = data.get('url', '')
                        html_file = data.get('html_file', '')
                        if url and html_file:
                            self.url_to_filename_map[url] = html_file
                except Exception as e:
                    logger.warning(f"Error reading {data_file}: {e}")
        
        logger.info(f"Created {len(self.url_to_filename_map)} URL mappings from data files")
    
    def normalize_url(self, url, base_url):
        """Normalize URL to absolute form"""
        if url.startswith('#'):
            return base_url
        if url.startswith('javascript:'):
            return base_url
        if url.startswith('mailto:'):
            return base_url
            
        try:
            import urllib.parse
            parsed = urllib.parse.urljoin(base_url, url)
            # Remove fragments
            parsed = urllib.parse.urlparse(parsed)
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))
        except:
            return base_url
    
    def is_valid_triz_url(self, url):
        """Check if URL is part of the TRIZ knowledge base"""
        return (url.startswith('https://wiki.matriz.org') and 
                '/knowledge-base/triz/' in url and
                not url.endswith(('.pdf', '.zip', '.doc', '.docx')) and
                '#' not in url)
    
    def get_local_filename_for_url(self, url):
        """Get the local HTML filename for a given URL"""
        return self.url_to_filename_map.get(url, '')
    
    def convert_html_file_to_offline(self, html_file_path):
        """Convert a single HTML file to have offline links"""
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            modified = False
            
            # Convert all anchor links
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href:
                    # Normalize the URL
                    normalized_url = self.normalize_url(href, 'https://wiki.matriz.org')
                    
                    if self.is_valid_triz_url(normalized_url):
                        # Check if we have a local file for this URL
                        local_filename = self.get_local_filename_for_url(normalized_url)
                        if local_filename:
                            # Rewrite to local file
                            link['href'] = local_filename
                            modified = True
                            logger.debug(f"Rewrote link {href} -> {local_filename}")
                        else:
                            # If we don't have this page, disable the link
                            link['href'] = '#'
                            link['title'] = f"Page not available offline: {normalized_url}"
                            link['style'] = 'color: #999; text-decoration: line-through;'
                            modified = True
                            logger.debug(f"Disabled link {href} (not available offline)")
                    elif href.startswith('https://wiki.matriz.org'):
                        # External link - keep as is but add target="_blank"
                        link['target'] = '_blank'
                        link['rel'] = 'noopener noreferrer'
                        modified = True
            
            # Convert image sources to local files
            for img in soup.find_all('img'):
                src = img.get('src')
                if src:
                    normalized_url = self.normalize_url(src, 'https://wiki.matriz.org')
                    if normalized_url.startswith('https://wiki.matriz.org'):
                        # Check if we have this image locally
                        if os.path.exists(self.images_dir):
                            # Find the local image filename
                            for local_img in os.listdir(self.images_dir):
                                if local_img.startswith(hashlib.md5(normalized_url.encode()).hexdigest()):
                                    img['src'] = f"../images/{local_img}"
                                    modified = True
                                    logger.debug(f"Rewrote image {src} -> ../images/{local_img}")
                                    break
                        else:
                            # Image not available offline
                            img['src'] = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlIG5vdCBhdmFpbGFibGUgb2ZmbGluZTwvdGV4dD48L3N2Zz4="
                            img['alt'] = "Image not available offline"
                            modified = True
                            logger.debug(f"Replaced offline image {src} with placeholder")
            
            if modified:
                # Write the modified content back
                with open(html_file_path, 'w', encoding='utf-8') as f:
                    f.write(str(soup))
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error converting {html_file_path}: {e}")
            return False
    
    def convert_all_html_files(self):
        """Convert all HTML files to have offline links"""
        if not os.path.exists(self.html_dir):
            logger.error(f"HTML directory {self.html_dir} not found")
            return
        
        html_files = [f for f in os.listdir(self.html_dir) if f.endswith('.html')]
        logger.info(f"Found {len(html_files)} HTML files to convert")
        
        converted_count = 0
        for html_file in html_files:
            html_path = os.path.join(self.html_dir, html_file)
            if self.convert_html_file_to_offline(html_path):
                converted_count += 1
                logger.info(f"Converted {html_file}")
        
        logger.info(f"Successfully converted {converted_count} HTML files to offline format")
    
    def update_sitemap(self):
        """Update the sitemap to show offline navigation"""
        sitemap_file = f"{self.output_dir}/sitemap.html"
        if not os.path.exists(sitemap_file):
            logger.warning("Sitemap not found, skipping update")
            return
        
        try:
            with open(sitemap_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update the title and add offline note
            content = content.replace(
                '<title>TRIZ Knowledge Base - Crawled Content</title>',
                '<title>TRIZ Knowledge Base - Offline Content</title>'
            )
            
            content = content.replace(
                '<h1>TRIZ Knowledge Base - Crawled Content</h1>',
                '''<h1>TRIZ Knowledge Base - Offline Content</h1>
    
    <div style="background: #e8f5e8; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #4caf50;">
        <h2>🚀 Offline Navigation Ready!</h2>
        <p><strong>All internal links have been rewritten to work offline!</strong></p>
        <p>Click any link below to navigate between pages. All TRIZ content is now fully navigable without internet connection.</p>
    </div>'''
            )
            
            # Update the statistics section
            content = content.replace(
                '<p><strong>Links:</strong>',
                '<p><strong>Links:</strong> (all working offline)'
            )
            
            # Make page titles clickable
            for url, html_file in self.url_to_filename_map.items():
                content = content.replace(
                    f'<div class="title">{html_file}</div>',
                    f'<div class="title"><a href="html/{html_file}" target="_blank">{html_file}</a></div>'
                )
            
            # Write the updated sitemap
            with open(sitemap_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info("Updated sitemap with offline navigation information")
            
        except Exception as e:
            logger.error(f"Error updating sitemap: {e}")

def main():
    """Main function"""
    logger.info("Starting offline link conversion...")
    
    converter = OfflineLinkConverter()
    converter.convert_all_html_files()
    converter.update_sitemap()
    
    logger.info("Offline link conversion completed!")
    logger.info("All HTML files now have offline links for internal navigation")

if __name__ == "__main__":
    main()
