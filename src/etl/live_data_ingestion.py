"""
Live Data Ingestion Module
Fetches real-time data from multiple job board APIs
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
from typing import List, Dict, Any, Optional
import os
from dataclasses import dataclass
import json

from utils.mongodb_client import MongoDBClient
from config.settings import get_settings

logger = logging.getLogger(__name__)

@dataclass
class JobData:
    """Standardized job data structure"""
    title: str
    company: str
    location: str
    salary_min: Optional[int]
    salary_max: Optional[int]
    currency: str
    description: str
    skills: List[str]
    experience_required: Optional[str]
    job_type: str
    posted_date: datetime
    source: str
    source_id: str
    url: str

class AdzunaAPIClient:
    """Adzuna Job Board API Client"""
    
    def __init__(self):
        self.settings = get_settings()
        self.app_id = os.getenv('ADZUNA_APP_ID')
        self.app_key = os.getenv('ADZUNA_APP_KEY')
        self.base_url = "https://api.adzuna.com/v1/api/jobs"
        
        if not self.app_id or not self.app_key:
            logger.warning("Adzuna API credentials not found")
    
    def fetch_jobs(self, country: str = "in", limit: int = 100, page: int = 1) -> List[JobData]:
        """Fetch jobs from Adzuna API"""
        if not self.app_id or not self.app_key:
            logger.error("Adzuna API credentials missing")
            return []
        
        try:
            url = f"{self.base_url}/{country}/search/{page}"
            params = {
                'app_id': self.app_id,
                'app_key': self.app_key,
                'results_per_page': min(limit, 50),  # Adzuna max is 50
                'sort_by': 'date',
                'content-type': 'application/json'
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            jobs = []
            
            for job_raw in data.get('results', []):
                try:
                    # Extract skills from description using simple keyword matching
                    skills = self._extract_skills_from_description(job_raw.get('description', ''))
                    
                    # Parse salary
                    salary_min, salary_max = self._parse_salary(job_raw)
                    
                    job = JobData(
                        title=job_raw.get('title', '').strip(),
                        company=job_raw.get('company', {}).get('display_name', '').strip(),
                        location=job_raw.get('location', {}).get('display_name', '').strip(),
                        salary_min=salary_min,
                        salary_max=salary_max,
                        currency='INR',  # Assuming Indian jobs
                        description=job_raw.get('description', '').strip()[:1000],  # Limit description
                        skills=skills,
                        experience_required=self._extract_experience(job_raw.get('description', '')),
                        job_type=job_raw.get('contract_type', 'full_time'),
                        posted_date=self._parse_date(job_raw.get('created')),
                        source='adzuna',
                        source_id=str(job_raw.get('id', '')),
                        url=job_raw.get('redirect_url', '')
                    )
                    jobs.append(job)
                    
                except Exception as e:
                    logger.warning(f"Error parsing job: {e}")
                    continue
            
            logger.info(f"Fetched {len(jobs)} jobs from Adzuna")
            return jobs
            
        except requests.RequestException as e:
            logger.error(f"Adzuna API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in Adzuna fetch: {e}")
            return []
    
    def _extract_skills_from_description(self, description: str) -> List[str]:
        """Extract skills from job description using keyword matching"""
        if not description:
            return []
        
        # Common tech skills to look for
        skill_keywords = [
            'python', 'java', 'javascript', 'react', 'node.js', 'angular', 'vue.js',
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins',
            'machine learning', 'data science', 'artificial intelligence',
            'html', 'css', 'bootstrap', 'tailwind', 'sass',
            'git', 'github', 'gitlab', 'jira', 'confluence',
            'agile', 'scrum', 'devops', 'ci/cd', 'terraform',
            'spring boot', 'django', 'flask', 'express.js',
            'pandas', 'numpy', 'scikit-learn', 'tensorflow', 'pytorch'
        ]
        
        description_lower = description.lower()
        found_skills = []
        
        for skill in skill_keywords:
            if skill.lower() in description_lower:
                found_skills.append(skill.title())
        
        return list(set(found_skills))  # Remove duplicates
    
    def _parse_salary(self, job_data: Dict) -> tuple[Optional[int], Optional[int]]:
        """Parse salary information from job data"""
        try:
            salary_min = job_data.get('salary_min')
            salary_max = job_data.get('salary_max')
            
            # Convert to INR if needed (Adzuna might return in other currencies)
            if salary_min:
                salary_min = int(float(salary_min))
            if salary_max:
                salary_max = int(float(salary_max))
            
            return salary_min, salary_max
        except (ValueError, TypeError):
            return None, None
    
    def _extract_experience(self, description: str) -> Optional[str]:
        """Extract experience requirements from description"""
        if not description:
            return None
        
        description_lower = description.lower()
        
        # Look for experience patterns
        experience_patterns = [
            'fresher', 'entry level', '0-1 years', '0-2 years',
            '1-3 years', '2-4 years', '3-5 years', '5+ years',
            'senior', 'lead', 'principal', 'architect'
        ]
        
        for pattern in experience_patterns:
            if pattern in description_lower:
                return pattern.title()
        
        return None
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime"""
        try:
            if date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return datetime.now()
        except:
            return datetime.now()

class IndeedScraperClient:
    """Indeed Job Scraper (Web Scraping)"""
    
    def __init__(self):
        self.base_url = "https://in.indeed.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def fetch_jobs(self, query: str = "software engineer", location: str = "India", limit: int = 50) -> List[JobData]:
        """Fetch jobs from Indeed (simplified scraping)"""
        # Note: This is a simplified implementation
        # In production, you'd want to use proper scraping tools like Scrapy
        # and handle rate limiting, proxies, etc.
        
        logger.info(f"Indeed scraping not implemented in this demo - would fetch {limit} jobs for '{query}' in {location}")
        return []  # Return empty for now

class LiveDataIngestion:
    """Main class for live data ingestion from multiple sources"""
    
    def __init__(self):
        self.mongodb_client = MongoDBClient()
        self.adzuna_client = AdzunaAPIClient()
        self.indeed_client = IndeedScraperClient()
        
        # Connect to MongoDB
        if not self.mongodb_client.connect():
            logger.error("Failed to connect to MongoDB")
    
    def fetch_all_live_data(self, total_limit: int = 500) -> Dict[str, Any]:
        """Fetch live data from all sources"""
        logger.info(f"Starting live data ingestion (target: {total_limit} jobs)")
        
        results = {
            'jobs_fetched': 0,
            'skills_updated': 0,
            'sources': {},
            'timestamp': datetime.now().isoformat(),
            'errors': []
        }
        
        try:
            # Fetch from Adzuna (primary source)
            adzuna_limit = int(total_limit * 0.8)  # 80% from Adzuna
            adzuna_jobs = self.adzuna_client.fetch_jobs(limit=adzuna_limit)
            
            if adzuna_jobs:
                # Store jobs in MongoDB
                jobs_stored = self._store_jobs_in_mongodb(adzuna_jobs, 'adzuna')
                results['jobs_fetched'] += jobs_stored
                results['sources']['adzuna'] = jobs_stored
                
                # Extract and update skills
                skills_updated = self._update_skills_from_jobs(adzuna_jobs)
                results['skills_updated'] += skills_updated
            
            # Fetch from Indeed (if implemented)
            indeed_limit = total_limit - results['jobs_fetched']
            if indeed_limit > 0:
                indeed_jobs = self.indeed_client.fetch_jobs(limit=indeed_limit)
                if indeed_jobs:
                    jobs_stored = self._store_jobs_in_mongodb(indeed_jobs, 'indeed')
                    results['jobs_fetched'] += jobs_stored
                    results['sources']['indeed'] = jobs_stored
            
            logger.info(f"Live data ingestion completed: {results['jobs_fetched']} jobs, {results['skills_updated']} skills updated")
            
        except Exception as e:
            error_msg = f"Live data ingestion failed: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
        
        return results
    
    def _store_jobs_in_mongodb(self, jobs: List[JobData], source: str) -> int:
        """Store jobs in MongoDB with deduplication"""
        if not jobs:
            return 0
        
        try:
            collection = self.mongodb_client.get_collection('live_jobs')
            stored_count = 0
            
            for job in jobs:
                # Create document
                job_doc = {
                    'title': job.title,
                    'company': job.company,
                    'location': job.location,
                    'salary_min': job.salary_min,
                    'salary_max': job.salary_max,
                    'currency': job.currency,
                    'description': job.description,
                    'skills': job.skills,
                    'experience_required': job.experience_required,
                    'job_type': job.job_type,
                    'posted_date': job.posted_date,
                    'source': job.source,
                    'source_id': job.source_id,
                    'url': job.url,
                    'ingested_at': datetime.now(),
                    'is_active': True
                }
                
                # Upsert to avoid duplicates
                filter_query = {
                    'source': job.source,
                    'source_id': job.source_id
                }
                
                result = collection.update_one(
                    filter_query,
                    {'$set': job_doc},
                    upsert=True
                )
                
                if result.upserted_id or result.modified_count > 0:
                    stored_count += 1
            
            logger.info(f"Stored {stored_count} jobs from {source}")
            return stored_count
            
        except Exception as e:
            logger.error(f"Error storing jobs from {source}: {e}")
            return 0
    
    def _update_skills_from_jobs(self, jobs: List[JobData]) -> int:
        """Extract and update skills database from job listings"""
        if not jobs:
            return 0
        
        try:
            collection = self.mongodb_client.get_collection('live_skills')
            skills_updated = 0
            
            # Aggregate all skills from jobs
            skill_counts = {}
            for job in jobs:
                for skill in job.skills:
                    if skill:
                        skill_counts[skill] = skill_counts.get(skill, 0) + 1
            
            # Update skills collection
            for skill, count in skill_counts.items():
                skill_doc = {
                    'skill_name': skill,
                    'demand_count': count,
                    'last_seen': datetime.now(),
                    'source': 'live_jobs',
                    'is_trending': count > 5  # Mark as trending if seen in 5+ jobs
                }
                
                # Upsert skill
                result = collection.update_one(
                    {'skill_name': skill},
                    {
                        '$set': skill_doc,
                        '$inc': {'total_mentions': count}
                    },
                    upsert=True
                )
                
                if result.upserted_id or result.modified_count > 0:
                    skills_updated += 1
            
            logger.info(f"Updated {skills_updated} skills from job data")
            return skills_updated
            
        except Exception as e:
            logger.error(f"Error updating skills: {e}")
            return 0
    
    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get statistics about data ingestion"""
        try:
            jobs_collection = self.mongodb_client.get_collection('live_jobs')
            skills_collection = self.mongodb_client.get_collection('live_skills')
            
            # Get job stats
            total_jobs = jobs_collection.count_documents({})
            active_jobs = jobs_collection.count_documents({'is_active': True})
            
            # Get recent jobs (last 24 hours)
            yesterday = datetime.now() - timedelta(days=1)
            recent_jobs = jobs_collection.count_documents({
                'ingested_at': {'$gte': yesterday}
            })
            
            # Get skills stats
            total_skills = skills_collection.count_documents({})
            trending_skills = skills_collection.count_documents({'is_trending': True})
            
            # Get source breakdown
            source_pipeline = [
                {'$group': {'_id': '$source', 'count': {'$sum': 1}}},
                {'$sort': {'count': -1}}
            ]
            source_stats = list(jobs_collection.aggregate(source_pipeline))
            
            return {
                'total_jobs': total_jobs,
                'active_jobs': active_jobs,
                'recent_jobs_24h': recent_jobs,
                'total_skills': total_skills,
                'trending_skills': trending_skills,
                'source_breakdown': source_stats,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting ingestion stats: {e}")
            return {}

def main():
    """Main function for testing"""
    logging.basicConfig(level=logging.INFO)
    
    ingestion = LiveDataIngestion()
    results = ingestion.fetch_all_live_data(total_limit=100)
    
    print("Ingestion Results:")
    print(json.dumps(results, indent=2, default=str))
    
    stats = ingestion.get_ingestion_stats()
    print("\nIngestion Stats:")
    print(json.dumps(stats, indent=2, default=str))

if __name__ == "__main__":
    main()