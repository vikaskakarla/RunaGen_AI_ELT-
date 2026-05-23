"""
Free LinkedIn Scraper using Selenium
Bypasses anti-bot measures with headless browser
"""
import time
import logging
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LinkedInSeleniumScraper:
    """Free LinkedIn scraper using Selenium with headless Chrome"""
    
    def __init__(self, headless: bool = True):
        """
        Initialize Selenium scraper
        
        Args:
            headless: Run browser in headless mode (no GUI)
        """
        self.headless = headless
        self.driver = None
    
    def _init_driver(self):
        """Initialize Chrome driver with anti-detection settings"""
        if self.driver:
            return
        
        try:
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument('--headless')
            
            # Anti-detection settings
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Realistic user agent
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Window size
            chrome_options.add_argument('--window-size=1920,1080')
            
            # Disable images for faster loading
            prefs = {
                'profile.managed_default_content_settings.images': 2,
                'disk-cache-size': 4096
            }
            chrome_options.add_experimental_option('prefs', prefs)
            
            # Use webdriver-manager to auto-download correct ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute CDP commands to hide automation
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("✅ Chrome driver initialized successfully")
        
        except Exception as e:
            logger.error(f"❌ Failed to initialize Chrome driver: {e}")
            logger.info("💡 Install ChromeDriver: brew install chromedriver (Mac) or apt-get install chromium-chromedriver (Linux)")
            raise
    
    def scrape_public_profile(self, linkedin_url: str) -> Dict:
        """
        Scrape public LinkedIn profile (no login required)
        
        Args:
            linkedin_url: LinkedIn profile URL
        
        Returns:
            Dict with name, headline, certifications, skills, experience
        """
        try:
            self._init_driver()
            
            logger.info(f"🔍 Scraping LinkedIn profile: {linkedin_url}")
            
            # Navigate to profile
            self.driver.get(linkedin_url)
            time.sleep(3)  # Wait for page load
            
            profile_data = {
                'name': None,
                'headline': None,
                'certifications': [],
                'skills': [],
                'experience': [],
                'education': []
            }
            
            # Extract name - Try multiple selectors for public profiles
            name_selectors = [
                'h1.text-heading-xlarge', 
                'h1.top-card-layout__title', 
                'h1.authwall-base__title',
                'h1.public-profile-title',
                'h1.profile-top-card-hero-content__title'
            ]
            for selector in name_selectors:
                try:
                    name_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    profile_data['name'] = name_elem.text.strip()
                    logger.info(f"✅ Found name with {selector}: {profile_data['name']}")
                    break
                except NoSuchElementException:
                    continue
            
            if not profile_data['name']:
                logger.warning("⚠️ Could not find name element")
            
            # Extract headline - Try multiple selectors
            headline_selectors = [
                'div.text-body-medium', 
                'h2.top-card-layout__headline', 
                'h2.authwall-base__subtitle',
                'p.profile-top-card-hero-content__headline'
            ]
            for selector in headline_selectors:
                try:
                    headline_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    profile_data['headline'] = headline_elem.text.strip()
                    logger.info(f"✅ Found headline with {selector}: {profile_data['headline'][:50]}...")
                    break
                except NoSuchElementException:
                    continue
            
            if not profile_data['headline']:
                logger.warning("⚠️ Could not find headline")
            
            # Scroll to load more content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Extract certifications
            profile_data['certifications'] = self._extract_certifications()
            
            # Extract skills
            profile_data['skills'] = self._extract_skills()
            
            # Extract experience
            profile_data['experience'] = self._extract_experience()
            
            logger.info(f"✅ Scraped profile: {len(profile_data['certifications'])} certs, "
                       f"{len(profile_data['skills'])} skills, {len(profile_data['experience'])} experiences")
            
            return profile_data
        
        except Exception as e:
            logger.error(f"❌ Error scraping profile: {e}")
            import traceback
            traceback.print_exc()
            return {
                'name': None,
                'headline': None,
                'certifications': [],
                'skills': [],
                'experience': [],
                'education': []
            }
    
    def _extract_certifications(self) -> List[Dict]:
        """Extract certifications from profile with multiple selector strategies"""
        certifications = []
        
        # Strategy 1: Logged-in/Modern UI
        strategies = [
            # Strategy A: Standard Section ID
            {"section": "//section[contains(@id, 'licenses_and_certifications')]//li", 
             "name": "div.mr1 span[aria-hidden='true']", 
             "issuer": "span.t-14.t-normal span[aria-hidden='true']"},
            
            # Strategy B: Public Profile Layout 1
            {"section": "li.certification-item", 
             "name": "h3.certification-item__title", 
             "issuer": "h4.certification-item__subtitle"},
            
            # Strategy C: Profile V2 Public
            {"section": "li.profile-section-card", 
             "name": "h3.profile-section-card__title", 
             "issuer": "h4.profile-section-card__subtitle"}
        ]
        
        for strategy in strategies:
            try:
                if strategy['section'].startswith('//'):
                    items = self.driver.find_elements(By.XPATH, strategy['section'])
                else:
                    items = self.driver.find_elements(By.CSS_SELECTOR, strategy['section'])
                
                if items:
                    for item in items[:10]:
                        try:
                            name = item.find_element(By.CSS_SELECTOR, strategy['name']).text.strip()
                            issuer = item.find_element(By.CSS_SELECTOR, strategy['issuer']).text.strip()
                            if name and issuer:
                                certifications.append({
                                    'name': name,
                                    'issuer': issuer,
                                    'source': f'LinkedIn ({strategy["name"]})'
                                })
                                logger.info(f"  ✓ Found cert: {name}")
                        except NoSuchElementException:
                            continue
                    if certifications: break # Success with this strategy
            except Exception:
                continue
        
        # Final fallback: Look for any text containing "Certificate" or "License"
        if not certifications:
            try:
                text_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Certificate') or contains(text(), 'License')]/ancestor::li")
                for elem in text_elements[:5]:
                    text = elem.text.split('\n')
                    if len(text) >= 2:
                        certifications.append({
                            'name': text[0].strip(),
                            'issuer': text[1].strip(),
                            'source': 'LinkedIn (Text Fallback)'
                        })
            except Exception: pass
            
        return certifications
    
    def _extract_skills(self) -> List[str]:
        """Extract skills from profile"""
        skills = []
        
        try:
            skill_elements = self.driver.find_elements(By.XPATH, 
                "//section[contains(@id, 'skills')]//span[@aria-hidden='true']")
            
            for skill_elem in skill_elements[:20]:  # Limit to 20
                skill = skill_elem.text.strip()
                if skill and len(skill) > 2 and skill not in skills:
                    skills.append(skill)
        
        except Exception as e:
            logger.warning(f"⚠️ Could not extract skills: {e}")
        
        return skills
    
    def _extract_experience(self) -> List[Dict]:
        """Extract work experience from profile"""
        experiences = []
        
        try:
            exp_sections = self.driver.find_elements(By.XPATH, 
                "//section[contains(@id, 'experience')]//li")
            
            for exp_elem in exp_sections[:5]:  # Limit to 5
                try:
                    title_elem = exp_elem.find_element(By.CSS_SELECTOR, 'div.mr1 span[aria-hidden="true"]')
                    title = title_elem.text.strip()
                    
                    company_elem = exp_elem.find_element(By.CSS_SELECTOR, 'span.t-14.t-normal span[aria-hidden="true"]')
                    company = company_elem.text.strip()
                    
                    if title and company:
                        experiences.append({
                            'title': title,
                            'company': company
                        })
                
                except Exception as e:
                    logger.debug(f"Error parsing experience: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"⚠️ Could not extract experience: {e}")
        
        return experiences
    
    def close(self):
        """Close browser"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("✅ Browser closed")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            finally:
                self.driver = None
    
    def __del__(self):
        """Cleanup on deletion"""
        self.close()


# Global instance
_selenium_scraper = None

def get_selenium_scraper(headless: bool = True):
    """Get or create global Selenium scraper instance"""
    global _selenium_scraper
    if _selenium_scraper is None:
        _selenium_scraper = LinkedInSeleniumScraper(headless=headless)
    return _selenium_scraper
