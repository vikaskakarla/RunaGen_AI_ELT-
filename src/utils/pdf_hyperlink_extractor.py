"""
Enhanced PDF Parser with Hyperlink Extraction
Extracts both visible text and underlying hyperlinks from PDF files
"""
import io
import re
import logging
from typing import Dict, List, Optional, Tuple
import PyPDF2


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFHyperlinkExtractor:
    """Extract text and hyperlinks from PDF files"""
    
    def __init__(self):
        self.extracted_links = []
    
    def extract_text_and_links(self, pdf_content: bytes) -> Tuple[str, List[Dict]]:
        """
        Extract both text and hyperlinks from PDF
        
        Args:
            pdf_content: PDF file content as bytes
        
        Returns:
            Tuple of (extracted_text, list_of_hyperlinks)
            
        Example hyperlink dict:
            {
                'text': 'LinkedIn',
                'url': 'https://linkedin.com/in/username',
                'page': 1
            }
        """
        text = ""
        hyperlinks = []
        
        # Method 1: Try PyPDF2 for annotations (hyperlinks)
        try:
            logger.info("🔗 Extracting hyperlinks using PyPDF2...")
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
            
            for page_num, page in enumerate(pdf_reader.pages, start=1):
                # Extract text
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                
                # Extract annotations (links)
                if '/Annots' in page:
                    annotations = page['/Annots']
                    
                    for annotation in annotations:
                        try:
                            obj = annotation.get_object()
                            
                            # Check if it's a link annotation
                            if obj.get('/Subtype') == '/Link':
                                # Get the URL
                                url = None
                                if '/A' in obj:
                                    action = obj['/A']
                                    if '/URI' in action:
                                        url = action['/URI']
                                
                                # Get the link text (rectangle area)
                                link_text = None
                                if '/Rect' in obj:
                                    # The rect defines the clickable area
                                    # We'll try to extract text from that area
                                    rect = obj['/Rect']
                                    # For now, we'll just mark it as found
                                    link_text = "Link"
                                
                                if url:
                                    hyperlinks.append({
                                        'text': link_text or 'Link',
                                        'url': str(url),
                                        'page': page_num
                                    })
                                    logger.info(f"  ✓ Found hyperlink on page {page_num}: {url}")
                        
                        except Exception as e:
                            logger.debug(f"  ⚠️ Error parsing annotation: {e}")
                            continue
            
            logger.info(f"✅ PyPDF2: Extracted {len(hyperlinks)} hyperlinks")
        
        except Exception as e:
            logger.warning(f"⚠️ PyPDF2 extraction failed: {e}")
        
        # Method 2: Try pdfplumber for better text and hyperlink extraction
        try:
            import pdfplumber
            logger.info("🔗 Extracting hyperlinks using pdfplumber...")
            
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract text if not already extracted
                    if not text:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    
                    # Extract hyperlinks
                    if hasattr(page, 'hyperlinks'):
                        page_hyperlinks = page.hyperlinks
                        
                        for link in page_hyperlinks:
                            url = link.get('uri') or link.get('url')
                            link_text = link.get('text', 'Link')
                            
                            if url:
                                hyperlinks.append({
                                    'text': link_text,
                                    'url': str(url),
                                    'page': page_num
                                })
                                logger.info(f"  ✓ Found hyperlink on page {page_num}: {url}")
                    
                    # Also check annotations in pdfplumber
                    if hasattr(page, 'annots') and page.annots:
                        for annot in page.annots:
                            if annot.get('uri'):
                                url = annot['uri']
                                # Try to extract text from the annotation area
                                link_text = annot.get('title', 'Link')
                                
                                hyperlinks.append({
                                    'text': link_text,
                                    'url': str(url),
                                    'page': page_num
                                })
                                logger.info(f"  ✓ Found annotation link on page {page_num}: {url}")
            
            logger.info(f"✅ pdfplumber: Total {len(hyperlinks)} hyperlinks extracted")
        
        except Exception as e:
            logger.warning(f"⚠️ pdfplumber extraction failed: {e}")
        
        # Deduplicate hyperlinks
        unique_links = []
        seen_urls = set()
        
        for link in hyperlinks:
            url = link['url']
            if url not in seen_urls:
                seen_urls.add(url)
                unique_links.append(link)
        
        logger.info(f"✅ Total unique hyperlinks: {len(unique_links)}")
        
        return text, unique_links
    
    def extract_social_links_from_hyperlinks(
        self, 
        hyperlinks: List[Dict]
    ) -> Dict[str, Optional[str]]:
        """
        Extract LinkedIn, GitHub, and portfolio links from hyperlink list
        
        Args:
            hyperlinks: List of hyperlink dicts with 'url' and 'text'
        
        Returns:
            Dict with 'linkedin', 'github', 'portfolio' URLs
        """
        social_links = {
            'linkedin': None,
            'github': None,
            'portfolio': None,
            'verification_links': []
        }
        
        for link in hyperlinks:
            url = link['url'].lower().strip()
            # Clean trailing slashes
            if url.endswith('/'):
                url = url[:-1]
                
            # LinkedIn - looking for profile patterns
            # Must be linkedin.com/in/X or linkedin.com/pub/X or similar
            if 'linkedin.com' in url and not social_links['linkedin']:
                # Ensure it's not just a generic link to linkedin.com
                if any(p in url for p in ['/in/', '/pub/', '/profile/']) or len(url.split('linkedin.com/')) > 1:
                    path = url.split('linkedin.com/')[-1]
                    if path and path not in ['', '/', 'jobs', 'feed', 'school', 'company']:
                        social_links['linkedin'] = link['url']
                        logger.info(f"✅ Found exact LinkedIn profile: {link['url']}")
            
            # GitHub - looking for user profile
            elif 'github.com' in url and not social_links['github']:
                # Exclude common GitHub static pages
                excluded_github = [
                    '/features', '/pricing', '/about', '/contact', '/login', 
                    '/signup', '/trending', '/explore', '/marketplace'
                ]
                if not any(path in url for path in excluded_github):
                    path = url.split('github.com/')[-1]
                    # Ensure there's a username (not just github.com)
                    if path and '/' not in path: # Direct user link
                        social_links['github'] = link['url']
                        logger.info(f"✅ Found exact GitHub profile: {link['url']}")
                    elif path and path.count('/') == 1: # Repo link, still useful as it identifies user
                        social_links['github'] = f"https://github.com/{path.split('/')[0]}"
                        logger.info(f"✅ Found GitHub user from repo: {social_links['github']}")
            
            # Portfolio (any other domain that's not LinkedIn/GitHub)
            elif not social_links['portfolio']:
                # Check if it's a personal website (not common domains)
                excluded_domains = [
                    'linkedin.com', 'github.com', 'google.com', 'gmail.com',
                    'facebook.com', 'twitter.com', 'instagram.com',
                    'youtube.com', 'microsoft.com', 'apple.com', 'adobe.com'
                ]
                
                # Check if it looks like a valid http/https URL and not just a domain name
                if re.match(r'^https?://', url):
                    # Basic sanity check for domain name (at least one dot and some length)
                    domain_match = re.search(r'https?://([^/]+)', url)
                    if domain_match:
                        domain = domain_match.group(1)
                        if '.' in domain and len(domain) > 4:
                            if not any(ex in domain for ex in excluded_domains):
                                social_links['portfolio'] = link['url']
                                logger.info(f"✅ Found Portfolio from hyperlink: {link['url']}")
            
            # Certification Verification Links
            cert_domains = ['credly.com', 'verify.skilljar.com', 'coursera.org/verify', 'udemy.com/certificate', 'microsoft.com/learn']
            if any(domain in url for domain in cert_domains):
                social_links['verification_links'].append({
                    'url': link['url'],
                    'text': link['text']
                })
                logger.info(f"✅ Found Certification Verification Link: {link['url']}")
        
        return social_links
    
    def extract_all_links_from_text(self, text: str) -> Dict[str, Optional[str]]:
        """
        Fallback: Extract links from plain text using regex
        (for cases where hyperlinks aren't properly embedded)
        
        Args:
            text: Plain text extracted from PDF
        
        Returns:
            Dict with 'linkedin', 'github', 'portfolio' URLs
        """
        social_links = {
            'linkedin': None,
            'github': None,
            'portfolio': None
        }
        
        # LinkedIn patterns
        linkedin_patterns = [
            r'https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9\-]+)',
            r'linkedin\.com/in/([a-zA-Z0-9\-]+)',
        ]
        
        for pattern in linkedin_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.group(0).startswith('http'):
                    social_links['linkedin'] = match.group(0)
                else:
                    username = match.group(1)
                    social_links['linkedin'] = f"https://www.linkedin.com/in/{username}"
                logger.info(f"✅ Found LinkedIn from text: {social_links['linkedin']}")
                break
        
        # GitHub patterns
        github_patterns = [
            r'https?://(?:www\.)?github\.com/([a-zA-Z0-9\-]+)',
            r'github\.com/([a-zA-Z0-9\-]+)',
        ]
        
        for pattern in github_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                username = match.group(1)
                # Exclude common paths
                if username.lower() not in ['features', 'pricing', 'about', 'contact']:
                    if match.group(0).startswith('http'):
                        social_links['github'] = match.group(0)
                    else:
                        social_links['github'] = f"https://github.com/{username}"
                    logger.info(f"✅ Found GitHub from text: {social_links['github']}")
                    break
        
        return social_links
    
    def extract_complete_social_links(
        self, 
        pdf_content: bytes
    ) -> Tuple[str, Dict[str, Optional[str]], List[Dict]]:
        """
        Complete extraction: text, hyperlinks, and social links
        
        Args:
            pdf_content: PDF file content as bytes
        
        Returns:
            Tuple of (text, social_links_dict, all_hyperlinks)
        """
        logger.info("🚀 Starting complete PDF extraction with hyperlink support...")
        
        # Extract text and hyperlinks
        text, hyperlinks = self.extract_text_and_links(pdf_content)
        
        # Extract social links from hyperlinks first (most reliable)
        social_links = self.extract_social_links_from_hyperlinks(hyperlinks)
        
        # Fallback: Extract from plain text if not found in hyperlinks
        text_links = self.extract_all_links_from_text(text)
        
        # Merge results (prefer hyperlink extraction)
        for key in social_links:
            if not social_links[key] and text_links.get(key):
                social_links[key] = text_links[key]
                logger.info(f"✅ Using text-extracted {key}: {text_links[key]}")
        
        logger.info(f"✅ Extraction complete:")
        logger.info(f"   - Text: {len(text)} characters")
        logger.info(f"   - Hyperlinks: {len(hyperlinks)}")
        logger.info(f"   - LinkedIn: {social_links['linkedin']}")
        logger.info(f"   - GitHub: {social_links['github']}")
        logger.info(f"   - Portfolio: {social_links['portfolio']}")
        
        return text, social_links, hyperlinks


# Global instance
_pdf_extractor = None

def get_pdf_extractor():
    """Get or create global PDF extractor instance"""
    global _pdf_extractor
    if _pdf_extractor is None:
        _pdf_extractor = PDFHyperlinkExtractor()
    return _pdf_extractor
