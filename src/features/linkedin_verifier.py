"""
LinkedIn Profile Verifier
Extracts LinkedIn URL from resume and verifies certifications
"""
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LinkedInVerifier:
    """Verify certifications by scraping LinkedIn profile"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def extract_social_links(self, resume_text: str) -> Dict[str, Optional[str]]:
        """
        Extract LinkedIn, GitHub, and other social profile links from resume
        
        Returns:
            Dict with 'linkedin', 'github', 'portfolio' URLs
        """
        links = {
            'linkedin': None,
            'github': None,
            'portfolio': None
        }
        
        # LinkedIn patterns
        linkedin_patterns = [
            r'linkedin\.com/in/([a-zA-Z0-9\-]+)',
            r'linkedin\.com/pub/([a-zA-Z0-9\-]+)',
            r'www\.linkedin\.com/in/([a-zA-Z0-9\-]+)',
            r'https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9\-]+)',
        ]
        
        for pattern in linkedin_patterns:
            match = re.search(pattern, resume_text, re.IGNORECASE)
            if match:
                username = match.group(1)
                links['linkedin'] = f"https://www.linkedin.com/in/{username}"
                logger.info(f"✅ Found LinkedIn: {links['linkedin']}")
                break
        
        # GitHub patterns
        github_patterns = [
            r'github\.com/([a-zA-Z0-9\-]+)',
            r'www\.github\.com/([a-zA-Z0-9\-]+)',
            r'https?://(?:www\.)?github\.com/([a-zA-Z0-9\-]+)',
        ]
        
        for pattern in github_patterns:
            match = re.search(pattern, resume_text, re.IGNORECASE)
            if match:
                username = match.group(1)
                # Exclude common GitHub paths
                if username.lower() not in ['features', 'pricing', 'about', 'contact', 'login', 'signup']:
                    links['github'] = f"https://github.com/{username}"
                    logger.info(f"✅ Found GitHub: {links['github']}")
                    break
        
        # Portfolio/Personal website patterns
        portfolio_patterns = [
            r'https?://(?:www\.)?([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})',
            r'(?:portfolio|website|blog):\s*([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})',
        ]
        
        for pattern in portfolio_patterns:
            match = re.search(pattern, resume_text, re.IGNORECASE)
            if match:
                url = match.group(0) if match.group(0).startswith('http') else f"https://{match.group(1)}"
                # Exclude common domains
                if not any(domain in url.lower() for domain in ['linkedin.com', 'github.com', 'google.com', 'gmail.com']):
                    links['portfolio'] = url
                    logger.info(f"✅ Found Portfolio: {links['portfolio']}")
                    break
        
        return links
    
    def scrape_linkedin_certifications(self, linkedin_url: str) -> List[Dict]:
        """
        Scrape certifications from LinkedIn profile
        
        Tries multiple methods:
        1. Basic requests (fast but often blocked)
        2. Selenium scraper (slower but works)
        
        Returns:
            List of certifications with name, issuer, date
        """
        certifications = []
        
        # Method 1: Try basic requests first (fast)
        try:
            logger.info(f"🔍 Method 1: Trying basic HTTP request...")
            
            response = requests.get(linkedin_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # LinkedIn's HTML structure (may change frequently)
                cert_sections = soup.find_all('section', {'class': re.compile(r'certifications|licenses')})
                
                for section in cert_sections:
                    cert_items = section.find_all('li')
                    
                    for item in cert_items:
                        try:
                            name = item.find('h3').text.strip() if item.find('h3') else None
                            issuer = item.find('h4').text.strip() if item.find('h4') else None
                            date_elem = item.find('time')
                            date = date_elem.text.strip() if date_elem else None
                            
                            if name and issuer:
                                certifications.append({
                                    'name': name,
                                    'issuer': issuer,
                                    'date': date,
                                    'source': 'LinkedIn (HTTP)',
                                    'verified': True
                                })
                        except Exception as e:
                            logger.warning(f"Error parsing certification item: {e}")
                            continue
                
                if certifications:
                    logger.info(f"✅ Method 1 success: Found {len(certifications)} certifications")
                    return certifications
                else:
                    logger.warning(f"⚠️ Method 1: No certifications found in HTML")
            else:
                logger.warning(f"⚠️ Method 1 failed: HTTP {response.status_code}")
        
        except Exception as e:
            logger.warning(f"⚠️ Method 1 failed: {e}")
        
        # Method 2: Try Selenium scraper (more reliable but slower)
        try:
            logger.info(f"🔍 Method 2: Trying Selenium scraper...")
            
            from features.linkedin_scraper_selenium import get_selenium_scraper
            
            scraper = get_selenium_scraper(headless=True)
            profile_data = scraper.scrape_public_profile(linkedin_url)
            
            certifications = profile_data.get('certifications', [])
            
            if certifications:
                logger.info(f"✅ Method 2 success: Found {len(certifications)} certifications via Selenium")
            else:
                logger.warning(f"⚠️ Method 2: No certifications found")
            
            # Don't close scraper here - reuse for next request
            # scraper.close()
        
        except ImportError:
            logger.error(f"❌ Selenium not installed. Install with: pip install selenium")
        except Exception as e:
            logger.error(f"❌ Method 2 failed: {e}")
            import traceback
            traceback.print_exc()
        
        return certifications
    
    def verify_certifications(
        self, 
        resume_certs: List[Dict], 
        linkedin_certs: List[Dict]
    ) -> Tuple[List[Dict], List[str]]:
        """
        Cross-verify resume certifications with LinkedIn certifications
        
        Args:
            resume_certs: Certifications extracted from resume
            linkedin_certs: Certifications scraped from LinkedIn
        
        Returns:
            Tuple of (verified_certs, verification_notes)
        """
        verified_certs = []
        verification_notes = []
        
        # Create a set of LinkedIn cert names (lowercase for matching)
        linkedin_cert_names = {cert['name'].lower() for cert in linkedin_certs}
        
        for resume_cert in resume_certs:
            cert_name_lower = resume_cert.get('name', '').lower()
            
            # Check if certification exists in LinkedIn
            if cert_name_lower in linkedin_cert_names:
                resume_cert['linkedin_verified'] = True
                resume_cert['verification_source'] = 'LinkedIn Profile'
                verification_notes.append(f"✅ Verified: {resume_cert['name']}")
            else:
                resume_cert['linkedin_verified'] = False
                resume_cert['verification_source'] = 'Resume Only'
                verification_notes.append(f"⚠️ Not found on LinkedIn: {resume_cert['name']}")
            
            verified_certs.append(resume_cert)
        
        # Add certifications found on LinkedIn but not in resume
        for linkedin_cert in linkedin_certs:
            cert_name_lower = linkedin_cert['name'].lower()
            
            # Check if already in resume
            if not any(cert['name'].lower() == cert_name_lower for cert in resume_certs):
                linkedin_cert['linkedin_verified'] = True
                linkedin_cert['verification_source'] = 'LinkedIn Only'
                linkedin_cert['in_resume'] = False
                verified_certs.append(linkedin_cert)
                verification_notes.append(f"📌 Found on LinkedIn (not in resume): {linkedin_cert['name']}")
        
        return verified_certs, verification_notes
    
    def generate_profile_recommendations(self, social_links: Dict[str, Optional[str]]) -> List[str]:
        """
        Generate recommendations based on missing social profiles
        
        Args:
            social_links: Dict with 'linkedin', 'github', 'portfolio' URLs
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        if not social_links.get('linkedin'):
            recommendations.append(
                "🔗 Add your LinkedIn profile URL to your resume for better verification and networking opportunities"
            )
        
        if not social_links.get('github'):
            recommendations.append(
                "💻 Include your GitHub profile to showcase your projects and code contributions"
            )
        
        if not social_links.get('portfolio'):
            recommendations.append(
                "🌐 Consider adding a personal portfolio website to highlight your work and achievements"
            )
        
        # If LinkedIn exists, recommend keeping it updated
        if social_links.get('linkedin'):
            recommendations.append(
                "✨ Keep your LinkedIn profile updated with latest certifications and achievements for automatic verification"
            )
        
        return recommendations
    
    def get_verification_summary(
        self, 
        resume_text: str, 
        resume_certs: List[Dict],
        pre_extracted_social_links: Optional[Dict[str, Optional[str]]] = None
    ) -> Dict:
        """
        Complete verification workflow
        
        Args:
            resume_text: Full resume text
            resume_certs: Certifications extracted from resume
            pre_extracted_social_links: Optional dict with already extracted links (e.g. from PDF hyperlinks)
        
        Returns:
            Dict with verified_certs, social_links, recommendations, notes
        """
        logger.info("🔍 Starting LinkedIn verification workflow...")
        
        # Extract social links from text
        social_links = self.extract_social_links(resume_text)
        
        # Merge with pre-extracted links (which are more reliable as they come from hyperlinks)
        if pre_extracted_social_links:
            for key, value in pre_extracted_social_links.items():
                if value and not social_links.get(key):
                    social_links[key] = value
                    logger.info(f"✅ Using pre-extracted {key}: {value}")
        
        logger.info(f"📊 Final social links: {social_links}")
        
        # Try to scrape LinkedIn if available
        linkedin_certs = []
        if social_links.get('linkedin'):
            logger.info(f"🔗 LinkedIn profile found, attempting to scrape...")
            linkedin_certs = self.scrape_linkedin_certifications(social_links['linkedin'])
        else:
            logger.info("⚠️ No LinkedIn profile found in resume")
        
        # Verify certifications
        verified_certs, verification_notes = self.verify_certifications(
            resume_certs, 
            linkedin_certs
        )
        logger.info(f"✅ Verified {len(verified_certs)} certifications")
        
        # Generate recommendations
        profile_recommendations = self.generate_profile_recommendations(social_links)
        logger.info(f"💡 Generated {len(profile_recommendations)} recommendations")
        
        result = {
            'verified_certifications': verified_certs,
            'social_links': social_links,
            'linkedin_certifications_found': len(linkedin_certs),
            'verification_notes': verification_notes,
            'profile_recommendations': profile_recommendations,
            'linkedin_available': social_links.get('linkedin') is not None,
            'github_available': social_links.get('github') is not None,
            'portfolio_available': social_links.get('portfolio') is not None
        }
        
        logger.info(f"✅ Verification complete: {result['linkedin_available']=}, {result['github_available']=}")
        return result


# Global instance
_linkedin_verifier = None

def get_linkedin_verifier():
    """Get or create global LinkedIn verifier instance"""
    global _linkedin_verifier
    if _linkedin_verifier is None:
        _linkedin_verifier = LinkedInVerifier()
    return _linkedin_verifier
