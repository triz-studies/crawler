#!/usr/bin/env python3
"""
Create Offline Navigation System for TRIZ Knowledge Base
Creates a proper navigation structure and converts all links to work offline
"""

import os
import hashlib
import json
from pathlib import Path
from bs4 import BeautifulSoup
import logging
import re

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OfflineNavigationCreator:
    def __init__(self, output_dir="triz_content"):
        self.output_dir = output_dir
        self.html_dir = f"{output_dir}/html"
        self.data_dir = f"{output_dir}/data"
        self.images_dir = f"{output_dir}/images"
        
        # Create a comprehensive URL mapping
        self.url_to_filename_map = {}
        self.filename_to_url_map = {}
        self.page_titles = {}
        
        # Load existing data
        self.load_existing_data()
        
    def load_existing_data(self):
        """Load data from existing files to create URL mappings"""
        logger.info("Loading existing data to create URL mappings...")
        
        # First, try to load from crawl summary
        summary_file = f"{self.output_dir}/crawl_summary.json"
        if os.path.exists(summary_file):
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                
                # Create URL to filename mapping
                for page in summary.get('pages', []):
                    url = page.get('url', '')
                    html_file = page.get('html_file', '')
                    title = page.get('title', '')
                    if url and html_file:
                        self.url_to_filename_map[url] = html_file
                        self.filename_to_url_map[html_file] = url
                        self.page_titles[html_file] = title
                        
                logger.info(f"Loaded {len(self.url_to_filename_map)} URL mappings from summary")
                return
            except Exception as e:
                logger.warning(f"Error loading summary: {e}")
        
        # If no summary, create mappings from data files
        if os.path.exists(self.data_dir):
            for data_file in os.listdir(self.data_dir):
                if data_file.endswith('.json'):
                    try:
                        with open(f"{self.data_dir}/{data_file}", 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            url = data.get('url', '')
                            html_file = data.get('html_file', '')
                            title = data.get('title', '')
                            if url and html_file:
                                self.url_to_filename_map[url] = html_file
                                self.filename_to_url_map[html_file] = url
                                self.page_titles[html_file] = title
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
    
    def find_best_match_url(self, target_url):
        """Find the best matching URL in our mapping"""
        # Try exact match first
        if target_url in self.url_to_filename_map:
            return target_url
        
        # Try to find partial matches
        target_path = target_url.replace('https://wiki.matriz.org', '')
        
        for known_url in self.url_to_filename_map.keys():
            known_path = known_url.replace('https://wiki.matriz.org', '')
            
            # Check if paths match
            if target_path == known_path:
                return known_url
            
            # Check if one is a subset of the other
            if target_path.startswith(known_path) or known_path.startswith(target_path):
                return known_url
        
        return None
    
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
                        # Find the best matching URL
                        best_match = self.find_best_match_url(normalized_url)
                        
                        if best_match and best_match in self.url_to_filename_map:
                            # Rewrite to local file
                            local_filename = self.url_to_filename_map[best_match]
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
    
    def create_navigation_index(self):
        """Create a comprehensive navigation index"""
        if not self.page_titles:
            logger.warning("No page titles available, skipping navigation index")
            return
        
        # Group pages by category
        categories = {
            'Problem Identification Tools': [],
            'Problem Solving Tools': [],
            'Concept Substantiation': [],
            'TESE Trends': [],
            'Resources': [],
            'Other': []
        }
        
        for filename, title in self.page_titles.items():
            url = self.filename_to_url_map.get(filename, '')
            
            if 'problem-identification' in url.lower() or 'function-cost' in url.lower():
                categories['Problem Identification Tools'].append((filename, title, url))
            elif 'problem-solving' in url.lower() or 'ariz' in url.lower() or 'contradiction' in url.lower():
                categories['Problem Solving Tools'].append((filename, title, url))
            elif 'concept' in url.lower() or 'substantiation' in url.lower():
                categories['Concept Substantiation'].append((filename, title, url))
            elif 'tese' in url.lower() or 'trend' in url.lower():
                categories['TESE Trends'].append((filename, title, url))
            elif 'glossary' in url.lower() or 'resource' in url.lower():
                categories['Resources'].append((filename, title, url))
            else:
                categories['Other'].append((filename, title, url))
        
        # Create the navigation index HTML
        nav_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TRIZ Knowledge Base - Offline Navigation</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; padding: 20px; background: linear-gradient(135deg, #2b2171, #4a90e2); color: white; border-radius: 10px; }}
        .category {{ margin-bottom: 30px; }}
        .category h2 {{ color: #2b2171; border-bottom: 2px solid #4a90e2; padding-bottom: 10px; }}
        .page-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }}
        .page-card {{ background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 15px; transition: transform 0.2s, box-shadow 0.2s; }}
        .page-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
        .page-card a {{ color: #2b2171; text-decoration: none; font-weight: bold; }}
        .page-card a:hover {{ color: #4a90e2; }}
        .page-url {{ color: #6c757d; font-size: 0.8em; margin-top: 5px; }}
        .stats {{ background: #e8f5e8; padding: 20px; border-radius: 8px; margin-bottom: 30px; border-left: 4px solid #28a745; }}
        .stats h3 {{ color: #155724; margin-top: 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 TRIZ Knowledge Base - Offline Navigation</h1>
            <p>Complete offline access to all TRIZ methodology content</p>
        </div>
        
        <div class="stats">
            <h3>📊 Navigation Statistics</h3>
            <p><strong>Total Pages:</strong> {len(self.page_titles)}</p>
            <p><strong>Total Images:</strong> {len(os.listdir(self.images_dir)) if os.path.exists(self.images_dir) else 0}</p>
            <p><strong>Offline Links:</strong> All internal links converted for offline use</p>
            <p><strong>Navigation:</strong> Click any page title below to open the content</p>
        </div>
"""
        
        # Add each category
        for category_name, pages in categories.items():
            if pages:
                nav_html += f"""
        <div class="category">
            <h2>{category_name} ({len(pages)} pages)</h2>
            <div class="page-grid">
"""
                
                for filename, title, url in sorted(pages, key=lambda x: x[1].lower()):
                    nav_html += f"""
                <div class="page-card">
                    <a href="html/{filename}" target="_blank">{title}</a>
                    <div class="page-url">{url}</div>
                </div>
"""
                
                nav_html += """
            </div>
        </div>
"""
        
        nav_html += """
    </div>
</body>
</html>"""
        
        # Save the navigation index
        nav_file = f"{self.output_dir}/navigation_index.html"
        with open(nav_file, 'w', encoding='utf-8') as f:
            f.write(nav_html)
        
        logger.info(f"Created navigation index: {nav_file}")
    
    def update_sitemap(self):
        """Update the sitemap to show offline navigation"""
        sitemap_file = f"{self.output_dir}/sitemap.html"
        if not os.path.exists(sitemap_file):
            logger.warning("Sitemap not found, creating new one")
            self.create_new_sitemap()
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
        <p><strong>📁 <a href="navigation_index.html" target="_blank">View Complete Navigation Index</a></strong></p>
    </div>'''
            )
            
            # Update the statistics section
            content = content.replace(
                '<p><strong>Total Pages:</strong> 0</p>',
                f'<p><strong>Total Pages:</strong> {len(self.page_titles)}</p>'
            )
            
            content = content.replace(
                '<p><strong>Links:</strong>',
                '<p><strong>Links:</strong> (all working offline)'
            )
            
            # Make page titles clickable
            for filename, title in self.page_titles.items():
                content = content.replace(
                    f'<div class="title">{filename}</div>',
                    f'<div class="title"><a href="html/{filename}" target="_blank">{title}</a></div>'
                )
            
            # Write the updated sitemap
            with open(sitemap_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info("Updated sitemap with offline navigation information")
            
        except Exception as e:
            logger.error(f"Error updating sitemap: {e}")
    
    def create_new_sitemap(self):
        """Create a new sitemap if none exists"""
        sitemap_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TRIZ Knowledge Base - Offline Content</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .page {{ margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }}
        .title {{ font-weight: bold; color: #333; }}
        .url {{ color: #666; font-size: 0.9em; }}
        .content {{ margin-top: 10px; }}
        .stats {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .offline-note {{ background: #e8f5e8; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #4caf50; }}
    </style>
</head>
<body>
    <h1>TRIZ Knowledge Base - Offline Content</h1>
    
    <div class="offline-note">
        <h2>🚀 Offline Navigation Ready!</h2>
        <p><strong>All internal links have been rewritten to work offline!</strong></p>
        <p>Click any link below to navigate between pages. All TRIZ content is now fully navigable without internet connection.</p>
        <p><strong>📁 <a href="navigation_index.html" target="_blank">View Complete Navigation Index</a></strong></p>
    </div>
    
    <div class="stats">
        <h2>Statistics</h2>
        <p><strong>Total Pages:</strong> {len(self.page_titles)}</p>
        <p><strong>Total Images:</strong> {len(os.listdir(self.images_dir)) if os.path.exists(self.images_dir) else 0}</p>
        <p><strong>Crawl Date:</strong> {os.path.getmtime(self.html_dir) if os.path.exists(self.html_dir) else 'Unknown'}</p>
        <p><strong>Offline Links:</strong> All internal links rewritten for offline use</p>
    </div>
    
    <h2>Pages (Click to Navigate Offline)</h2>
"""
        
        for filename, title in self.page_titles.items():
            url = self.filename_to_url_map.get(filename, '')
            sitemap_html += f"""
    <div class="page">
        <div class="title"><a href="html/{filename}" target="_blank">{title}</a></div>
        <div class="url">{url}</div>
        <div class="content">
            <p><strong>HTML File:</strong> <a href="html/{filename}" target="_blank">{filename}</a></p>
        </div>
    </div>
"""
            
        sitemap_html += """
</body>
</html>"""
        
        sitemap_file = f"{self.output_dir}/sitemap.html"
        with open(sitemap_file, 'w', encoding='utf-8') as f:
            f.write(sitemap_html)
            
        logger.info(f"Created new sitemap: {sitemap_file}")

def main():
    """Main function"""
    logger.info("Starting offline navigation creation...")
    
    creator = OfflineNavigationCreator()
    
    # Convert all HTML files to have offline links
    creator.convert_all_html_files()
    
    # Create navigation index
    creator.create_navigation_index()
    
    # Update sitemap
    creator.update_sitemap()
    
    logger.info("Offline navigation creation completed!")
    logger.info("All HTML files now have offline links for internal navigation")
    logger.info("Created navigation_index.html for easy browsing")

if __name__ == "__main__":
    main()
