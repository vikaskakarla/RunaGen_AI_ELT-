"""
Phase 3: Real-time Job Scraping & Market Intelligence
Scrapes job data from multiple sources and updates BigQuery
"""
import os
import sys
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobScraper:
    """Scrape jobs from multiple sources"""
    
    def __init__(self):
        """Initialize BigQuery client"""
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'credentials/bigquery-key.json')
        
        if os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.bq_client = bigquery.Client(
                credentials=credentials,
                project=os.getenv('GCP_PROJECT_ID', 'runagen-ai')
            )
        else:
            self.bq_client = bigquery.Client(project=os.getenv('GCP_PROJECT_ID', 'runagen-ai'))
        
        self.project_id = os.getenv('GCP_PROJECT_ID', 'runagen-ai')
        self.dataset = 'runagen_bronze'
    
    def scrape_linkedin_jobs(self, keywords: List[str], location: str = "India") -> List[Dict]:
        """Scrape LinkedIn jobs (using public API)"""
        logger.info(f"🔍 Scraping LinkedIn jobs for {keywords} in {location}...")
        
        jobs = []
        
        # Note: LinkedIn has strict scraping policies
        # Using RapidAPI or official LinkedIn API is recommended
        # This is a placeholder for the actual implementation
        
        logger.info(f"✓ Found {len(jobs)} LinkedIn jobs")
        return jobs
    
    def scrape_indeed_jobs(self, keywords: List[str], location: str = "India") -> List[Dict]:
        """Scrape Indeed jobs"""
        logger.info(f"🔍 Scraping Indeed jobs for {keywords} in {location}...")
        
        jobs = []
        
        try:
            for keyword in keywords:
                url = f"https://in.indeed.com/jobs?q={keyword}&l={location}"
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                response = requests.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Parse job listings
                job_cards = soup.find_all('div', class_='job_seen_beacon')
                
                for card in job_cards[:10]:  # Limit to 10 per keyword
                    try:
                        title = card.find('h2', class_='jobTitle').text.strip()
                        company = card.find('span', class_='companyName').text.strip()
                        location_text = card.find('div', class_='companyLocation').text.strip()
                        
                        job = {
                            'title': title,
                            'company': company,
                            'location': location_text,
                            'source': 'Indeed',
                            'scraped_at': datetime.now().isoformat(),
                            'keyword': keyword
                        }
                        jobs.append(job)
                    except Exception as e:
                        logger.warning(f"Error parsing job card: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Error scraping Indeed: {e}")
        
        logger.info(f"✓ Found {len(jobs)} Indeed jobs")
        return jobs
    
    def scrape_adzuna_jobs(self, keywords: List[str], location: str = "India", limit: int = 10) -> List[Dict]:
        """Scrape Adzuna jobs using API"""
        logger.info(f"🔍 Scraping Adzuna jobs for {keywords} in {location}...")
        
        jobs = []
        
        try:
            api_id = os.getenv('ADZUNA_APP_ID', '')
            api_key = os.getenv('ADZUNA_APP_KEY', '')
            
            if not api_id or not api_key:
                logger.warning("⚠️  Adzuna API credentials not configured, returning mock data")
                # Return mock data for testing
                for keyword in keywords[:2]:  # Limit to 2 keywords
                    for i in range(min(5, limit)):  # 5 jobs per keyword or limit
                        jobs.append({
                            'title': f"{keyword} - Position {i+1}",
                            'company': f"Tech Company {i+1}",
                            'location': location,
                            'description': f"Looking for {keyword} with 3+ years experience. Great opportunity to work with cutting-edge technologies.",
                            'salary_min': 600000 + (i * 100000),
                            'salary_max': 1200000 + (i * 100000),
                            'currency': 'INR',
                            'source': 'Adzuna (Mock)',
                            'url': f"https://example.com/job/{i}",
                            'scraped_at': datetime.now().isoformat(),
                            'keyword': keyword
                        })
                logger.info(f"✅ Returned {len(jobs)} mock jobs")
                return jobs
            
            for keyword in keywords:
                url = f"https://api.adzuna.com/v1/api/jobs/in/search/1"
                params = {
                    'app_id': api_id,
                    'app_key': api_key,
                    'what': keyword,
                    'where': location,
                    'results_per_page': min(limit, 10)
                }
                
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code != 200:
                    logger.warning(f"⚠️ Adzuna API returned status {response.status_code}")
                    continue
                
                data = response.json()
                
                for result in data.get('results', []):
                    # Safely extract all fields with proper defaults
                    job = {
                        'title': str(result.get('title', 'Position')).strip() if result.get('title') else 'Position',
                        'company': str(result.get('company', {}).get('display_name', 'Company')).strip() if result.get('company') else 'Company',
                        'location': str(result.get('location', {}).get('display_name', location)).strip() if result.get('location') else location,
                        'description': str(result.get('description', ''))[:200].strip() if result.get('description') else '',
                        'salary_min': int(result.get('salary_min', 0)) if (result.get('salary_min') and int(result.get('salary_min')) > 1000) else 0,
                        'salary_max': int(result.get('salary_max', 0)) if (result.get('salary_max') and int(result.get('salary_max')) > 1000) else 0,
                        'currency': 'INR',
                        'source': 'Adzuna',
                        'url': str(result.get('redirect_url', '#')).strip() if result.get('redirect_url') else '#',
                        'scraped_at': datetime.now().isoformat(),
                        'keyword': keyword
                    }
                    jobs.append(job)
        
        except Exception as e:
            logger.error(f"❌ Error scraping Adzuna: {e}")
            import traceback
            traceback.print_exc()
        
        logger.info(f"✅ Found {len(jobs)} Adzuna jobs")
        return jobs
    
    def scrape_github_jobs(self, keywords: List[str], location: str = "India") -> List[Dict]:
        """Scrape GitHub Jobs"""
        logger.info(f"🔍 Scraping GitHub jobs for {keywords}...")
        
        jobs = []
        
        try:
            for keyword in keywords:
                url = "https://jobs.github.com/positions.json"
                params = {
                    'description': keyword,
                    'location': location
                }
                
                response = requests.get(url, params=params, timeout=10)
                data = response.json()
                
                for result in data:
                    job = {
                        'title': result.get('title'),
                        'company': result.get('company'),
                        'location': result.get('location'),
                        'description': result.get('description'),
                        'source': 'GitHub Jobs',
                        'url': result.get('url'),
                        'scraped_at': datetime.now().isoformat(),
                        'keyword': keyword
                    }
                    jobs.append(job)
        
        except Exception as e:
            logger.error(f"Error scraping GitHub Jobs: {e}")
        
        logger.info(f"✓ Found {len(jobs)} GitHub jobs")
        return jobs
    
    def load_to_bigquery(self, jobs: List[Dict], table_name: str = "raw_jobs"):
        """Load scraped jobs to BigQuery Bronze layer"""
        if not jobs:
            logger.warning("No jobs to load")
            return
        
        logger.info(f"📤 Loading {len(jobs)} jobs to BigQuery...")
        
        try:
            df = pd.DataFrame(jobs)
            
            # Ensure required columns exist
            required_columns = [
                'title', 'company', 'location', 'description', 'source',
                'salary_min', 'salary_max', 'url', 'scraped_at', 'keyword'
            ]
            
            for col in required_columns:
                if col not in df.columns:
                    df[col] = None
            
            # Add job_id if not present
            if 'job_id' not in df.columns:
                df['job_id'] = df.index.astype(str) + '_' + df['source'] + '_' + pd.Timestamp.now().strftime('%Y%m%d%H%M%S')
            
            # Add metadata columns
            df['currency'] = 'INR'
            df['employment_type'] = 'Full-time'
            df['experience_level'] = 'Mid-level'
            df['requirements'] = df['keyword']  # Use keyword as requirements
            df['posted_date'] = pd.Timestamp.now()
            
            # Select only required columns
            final_columns = [
                'job_id', 'source', 'title', 'company', 'location', 'description',
                'requirements', 'salary_min', 'salary_max', 'currency',
                'employment_type', 'experience_level', 'posted_date', 'scraped_at', 'url'
            ]
            
            df = df[final_columns]
            
            table_id = f"{self.project_id}.{self.dataset}.{table_name}"
            
            # Define schema
            schema = [
                bigquery.SchemaField("job_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("source", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("title", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("company", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("location", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("requirements", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("salary_min", "FLOAT64", mode="NULLABLE"),
                bigquery.SchemaField("salary_max", "FLOAT64", mode="NULLABLE"),
                bigquery.SchemaField("currency", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("employment_type", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("experience_level", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("posted_date", "TIMESTAMP", mode="NULLABLE"),
                bigquery.SchemaField("scraped_at", "TIMESTAMP", mode="NULLABLE"),
                bigquery.SchemaField("url", "STRING", mode="NULLABLE"),
            ]
            
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                schema=schema
            )
            
            load_job = self.bq_client.load_table_from_dataframe(
                df, table_id, job_config=job_config
            )
            load_job.result()
            
            logger.info(f"✓ Loaded {len(jobs)} jobs to {table_id}")
        
        except Exception as e:
            logger.error(f"Error loading to BigQuery: {e}")
            import traceback
            traceback.print_exc()
    
    def run_scraping_pipeline(self, keywords: List[str] = None, location: str = "India"):
        """Run complete scraping pipeline"""
        if keywords is None:
            keywords = ['Data Scientist', 'Data Engineer', 'Backend Developer', 'Frontend Developer']
        
        logger.info("="*70)
        logger.info("🚀 Job Scraping Pipeline")
        logger.info("="*70)
        
        all_jobs = []
        
        # Scrape from multiple sources
        all_jobs.extend(self.scrape_indeed_jobs(keywords, location))
        all_jobs.extend(self.scrape_adzuna_jobs(keywords, location))
        all_jobs.extend(self.scrape_github_jobs(keywords, location))
        
        logger.info(f"\n📊 Total jobs scraped: {len(all_jobs)}")
        
        # Load to BigQuery
        if all_jobs:
            self.load_to_bigquery(all_jobs)
        
        logger.info("="*70 + "\n")
        
        return all_jobs


def main():
    """Main execution"""
    scraper = JobScraper()
    scraper.run_scraping_pipeline()


if __name__ == "__main__":
    main()
