"""
BigQuery Data Provider for API
Provides data from BigQuery data warehouse for resume analysis
"""
import os
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account
from typing import List, Dict, Optional
import logging
import pandas as pd

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BigQueryDataProvider:
    """Data provider using BigQuery as the source"""
    
    def __init__(self):
        """Initialize BigQuery client"""
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'credentials/bigquery-key.json')
        gcp_json = os.getenv('GCP_SERVICE_ACCOUNT_JSON')
        
        if gcp_json:
            try:
                import json
                info = json.loads(gcp_json)
                credentials = service_account.Credentials.from_service_account_info(info)
                self.bq_client = bigquery.Client(
                    credentials=credentials,
                    project=os.getenv('GCP_PROJECT_ID', 'runagen-ai')
                )
                logger.info("✓ BigQuery client initialized from GCP_SERVICE_ACCOUNT_JSON")
            except Exception as e:
                logger.error(f"Failed to initialize BigQuery from GCP_SERVICE_ACCOUNT_JSON: {e}")
                self.bq_client = bigquery.Client(project=os.getenv('GCP_PROJECT_ID', 'runagen-ai'))
        elif os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.bq_client = bigquery.Client(
                credentials=credentials,
                project=os.getenv('GCP_PROJECT_ID', 'runagen-ai')
            )
        else:
            self.bq_client = bigquery.Client(project=os.getenv('GCP_PROJECT_ID', 'runagen-ai'))
        
        self.project_id = os.getenv('GCP_PROJECT_ID', 'runagen-ai')
        self._skills_cache = None
        self._jobs_cache = None
    
    def get_all_skills(self) -> List[Dict]:
        """Get all skills from BigQuery"""
        if self._skills_cache is not None:
            return self._skills_cache
        
        try:
            query = f"""
            SELECT DISTINCT skill_name, skill_category
            FROM `{self.project_id}.runagen_bronze.raw_skills`
            WHERE skill_name IS NOT NULL
            LIMIT 1000
            """
            
            results = self.bq_client.query(query).to_dataframe()
            
            self._skills_cache = [
                {
                    'skill_name': row['skill_name'],
                    'category': row['skill_category'] or 'Other'
                }
                for _, row in results.iterrows()
            ]
            
            logger.info(f"✓ Loaded {len(self._skills_cache)} skills from BigQuery")
            return self._skills_cache
        
        except Exception as e:
            logger.error(f"Error loading skills from BigQuery: {e}")
            return []
    
    def search_jobs(self, title: str, location: str = "India", limit: int = 10) -> List[Dict]:
        """Search jobs from BigQuery - properly parse Adzuna JSON data"""
        try:
            # First, check if the table exists and has data
            check_query = f"""
            SELECT COUNT(*) as count
            FROM `{self.project_id}.runagen_bronze.raw_jobs`
            """
            
            try:
                count_result = self.bq_client.query(check_query).to_dataframe()
                total_count = count_result.iloc[0]['count'] if not count_result.empty else 0
                logger.info(f"📊 Total jobs in BigQuery: {total_count}")
                
                if total_count == 0:
                    logger.warning(f"⚠️ BigQuery table is empty. No jobs available.")
                    return []
            except Exception as check_error:
                logger.error(f"❌ Error checking table: {check_error}")
                return []
            
            # Build the query with proper JSON parsing for nested fields
            query = f"""
            SELECT 
                CAST(job_id AS STRING) as job_id,
                CAST(title AS STRING) as title,
                -- Parse company from JSON if it's a JSON string
                CASE 
                    WHEN company LIKE '%display_name%' THEN 
                        REGEXP_EXTRACT(company, r"'display_name':\\s*'([^']+)'")
                    ELSE CAST(company AS STRING)
                END as company,
                -- Parse location from JSON if it's a JSON string
                CASE 
                    WHEN location LIKE '%display_name%' THEN 
                        REGEXP_EXTRACT(location, r"'display_name':\\s*'([^']+)'")
                    ELSE CAST(location AS STRING)
                END as location,
                CAST(description AS STRING) as description,
                CAST(salary_min AS INT64) as salary_min,
                CAST(salary_max AS INT64) as salary_max,
                CASE 
                    WHEN currency IS NULL OR currency = '' THEN 'INR'
                    ELSE CAST(currency AS STRING)
                END as currency,
                -- CAST(employment_type AS STRING) as employment_type,
                -- CAST(experience_level AS STRING) as experience_level,
                CAST(url AS STRING) as url
            FROM `{self.project_id}.runagen_bronze.raw_jobs`
            WHERE title IS NOT NULL
                AND company IS NOT NULL
                AND (
                    LOWER(title) LIKE LOWER('%{title}%')
                    OR LOWER(description) LIKE LOWER('%{title}%')
                )
            ORDER BY scraped_at DESC
            LIMIT {limit}
            """
            
            logger.info(f"🔍 Searching for jobs with title: '{title}'")
            results = self.bq_client.query(query).to_dataframe()
            
            if results.empty:
                logger.warning(f"⚠️ No jobs found for '{title}' in BigQuery")
                return []
            
            jobs = []
            for idx, row in results.iterrows():
                try:
                    # Safely extract and convert each field
                    title_val = str(row.get('title', '')).strip()
                    company_val = str(row.get('company', '')).strip()
                    location_val = str(row.get('location', '')).strip()
                    description_val = str(row.get('description', '')).strip()[:200]
                    
                    # Handle salary conversion - show exact values from BigQuery
                    try:
                        salary_min_val = int(float(row.get('salary_min', 0))) if pd.notna(row.get('salary_min')) else 0
                    except (ValueError, TypeError):
                        salary_min_val = 0
                    
                    try:
                        salary_max_val = int(float(row.get('salary_max', 0))) if pd.notna(row.get('salary_max')) else 0
                    except (ValueError, TypeError):
                        salary_max_val = 0
                    
                    currency_val = str(row.get('currency', 'INR')).strip()
                    if not currency_val or currency_val == 'None':
                        currency_val = 'INR'
                    
                    url_val = str(row.get('url', '#')).strip()
                    
                    # Only add if we have title and company
                    if title_val and company_val and company_val != 'None':
                        job_dict = {
                            'title': title_val,
                            'company': company_val,
                            'location': location_val or location,
                            'description': description_val,
                            'salary_min': salary_min_val,
                            'salary_max': salary_max_val,
                            'currency': currency_val,
                            'url': url_val
                        }
                        jobs.append(job_dict)
                except Exception as row_error:
                    logger.warning(f"⚠️ Error processing row {idx}: {row_error}")
                    continue
            
            logger.info(f"✅ Found {len(jobs)} clean jobs matching '{title}'")
            return jobs
        
        except Exception as e:
            logger.error(f"❌ Error searching jobs from BigQuery: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_job_market_trends(self) -> Dict:
        """Get job market trends from BigQuery Gold layer"""
        try:
            query = f"""
            SELECT *
            FROM `{self.project_id}.runagen_gold.job_market_trends`
            ORDER BY trend_date DESC
            LIMIT 100
            """
            
            results = self.bq_client.query(query).to_dataframe()
            
            trends = []
            for _, row in results.iterrows():
                trends.append({
                    'date': str(row.get('trend_date', '')),
                    'role': str(row.get('role', '')),
                    'job_count': int(row.get('job_count', 0)) if pd.notna(row.get('job_count')) else 0,
                    'avg_salary': float(row.get('avg_salary', 0)) if (pd.notna(row.get('avg_salary')) and row.get('avg_salary') > 0) else 900000,
                    'growth_rate': float(row.get('growth_rate', 0)) if pd.notna(row.get('growth_rate')) else 0
                })
            
            return {'trends': trends}
        
        except Exception as e:
            logger.error(f"Error getting job market trends: {e}")
            return {'trends': []}
    
    def get_skill_demand_forecast(self) -> Dict:
        """Get skill demand forecast from BigQuery Gold layer"""
        try:
            query = f"""
            SELECT *
            FROM `{self.project_id}.runagen_gold.skill_demand_forecast`
            ORDER BY forecast_date DESC
            LIMIT 100
            """
            
            results = self.bq_client.query(query).to_dataframe()
            
            forecasts = []
            for _, row in results.iterrows():
                forecasts.append({
                    'skill': str(row.get('skill_name', '')),
                    'current_demand': int(row.get('current_demand', 0)) if pd.notna(row.get('current_demand')) else 0,
                    'forecasted_demand': int(row.get('forecasted_demand', 0)) if pd.notna(row.get('forecasted_demand')) else 0,
                    'growth_percentage': float(row.get('growth_percentage', 0)) if pd.notna(row.get('growth_percentage')) else 0,
                    'forecast_date': str(row.get('forecast_date', ''))
                })
            
            return {'forecasts': forecasts}
        
        except Exception as e:
            logger.error(f"Error getting skill demand forecast: {e}")
            return {'forecasts': []}
    
    def get_role_skill_mappings(self) -> Dict[str, List[str]]:
        """Get role-skill mappings from BigQuery"""
        try:
            query = f"""
            SELECT 
                title,
                requirements
            FROM `{self.project_id}.runagen_bronze.raw_jobs`
            WHERE requirements IS NOT NULL
            LIMIT 1000
            """
            
            results = self.bq_client.query(query).to_dataframe()
            
            role_skills = {}
            for _, row in results.iterrows():
                title = row['title']
                requirements = row['requirements']
                
                # Normalize role
                role = self._normalize_role_title(title)
                if role and requirements:
                    if role not in role_skills:
                        role_skills[role] = set()
                    
                    # Split requirements by comma
                    skills = [s.strip().lower() for s in str(requirements).split(',')]
                    role_skills[role].update(skills)
            
            # Convert sets to lists
            return {role: list(skills) for role, skills in role_skills.items()}
        
        except Exception as e:
            logger.error(f"Error getting role-skill mappings: {e}")
            return self._get_default_role_skills()
    
    def _normalize_role_title(self, title: str) -> Optional[str]:
        """Normalize job title to standard role"""
        title_lower = title.lower()
        
        if 'data scientist' in title_lower:
            return 'Data Scientist'
        elif 'data engineer' in title_lower:
            return 'Data Engineer'
        elif 'data analyst' in title_lower:
            return 'Data Analyst'
        elif 'backend' in title_lower:
            return 'Backend Developer'
        elif 'frontend' in title_lower:
            return 'Frontend Developer'
        elif 'full stack' in title_lower:
            return 'Full Stack Developer'
        elif 'devops' in title_lower:
            return 'DevOps Engineer'
        elif 'software engineer' in title_lower:
            return 'Software Engineer'
        
        return None
    
    def _get_default_role_skills(self) -> Dict[str, List[str]]:
        """Default role-skill mappings (fallback)"""
        return {
            'Data Scientist': ['python', 'machine learning', 'statistics', 'sql', 'tensorflow', 'pandas'],
            'Data Engineer': ['python', 'sql', 'spark', 'airflow', 'etl', 'bigquery'],
            'Data Analyst': ['python', 'sql', 'tableau', 'excel', 'power bi', 'statistics'],
            'Backend Developer': ['python', 'java', 'node.js', 'sql', 'rest api', 'docker'],
            'Frontend Developer': ['javascript', 'react', 'css', 'html', 'typescript', 'vue'],
            'Full Stack Developer': ['javascript', 'python', 'react', 'sql', 'docker', 'aws'],
            'DevOps Engineer': ['docker', 'kubernetes', 'aws', 'ci/cd', 'linux', 'terraform'],
            'Software Engineer': ['python', 'java', 'c++', 'design patterns', 'testing', 'git']
        }
    
    def get_salary_data_by_role(self, role: str) -> Dict:
        """Get salary data for a specific role"""
        try:
            query = f"""
            SELECT 
                AVG(salary_min) as avg_min,
                AVG(salary_max) as avg_max,
                MIN(salary_min) as min_salary,
                MAX(salary_max) as max_salary
            FROM `{self.project_id}.runagen_bronze.raw_jobs`
            WHERE LOWER(title) LIKE LOWER('%{role}%')
                AND salary_min > 0
                AND salary_max > 0
            """
            
            results = self.bq_client.query(query).to_dataframe()
            
            if not results.empty:
                row = results.iloc[0]
                return {
                    'min_salary': float(row['min_salary']),
                    'median_salary': (float(row['avg_min']) + float(row['avg_max'])) / 2,
                    'max_salary': float(row['max_salary']),
                    'currency': 'INR'
                }
        
        except Exception as e:
            logger.error(f"Error getting salary data: {e}")
        
        # Fallback
        salary_map = {
            'Data Scientist': {'min': 800000, 'median': 1200000, 'max': 1600000},
            'Data Engineer': {'min': 700000, 'median': 1000000, 'max': 1400000},
            'Data Analyst': {'min': 400000, 'median': 600000, 'max': 800000},
            'Backend Developer': {'min': 600000, 'median': 900000, 'max': 1300000},
            'Frontend Developer': {'min': 500000, 'median': 800000, 'max': 1200000}
        }
        
        data = salary_map.get(role, {'min': 500000, 'median': 800000, 'max': 1200000})
        return {
            'min_salary': data['min'],
            'median_salary': data['median'],
            'max_salary': data['max'],
            'currency': 'INR'
        }
    
    def get_company_salary(self, company: str, role: str = None) -> Dict:
        """Get salary data for a specific company from BigQuery"""
        try:
            # Clean company name for query
            clean_company = company.replace("'", "\\'")
            
            query = f"""
            SELECT 
                AVG(salary_min) as avg_min,
                AVG(salary_max) as avg_max
            FROM `{self.project_id}.runagen_bronze.raw_jobs`
            WHERE LOWER(company) LIKE LOWER('%{clean_company}%')
                AND salary_min > 10000
            """
            
            if role:
                query += f" AND LOWER(title) LIKE LOWER('%{role}%')"
                
            results = self.bq_client.query(query).to_dataframe()
            
            if not results.empty and pd.notna(results.iloc[0]['avg_min']):
                row = results.iloc[0]
                return {
                    'min': int(row['avg_min']),
                    'max': int(row['avg_max'] or row['avg_min'] * 1.2),
                    'source': 'Company Historical'
                }
        except Exception as e:
            logger.error(f"Error getting company salary: {e}")
        
        return None
    
    def get_suggested_jobs(self, role_name: str, limit: int = 5) -> List[Dict]:
        """Get suggested jobs matching a role - with fallback to live scraping"""
        logger.info(f"🔍 Searching for jobs matching role: {role_name}")
        jobs = self.search_jobs(role_name, location="India", limit=limit)
        
        if not jobs:
            logger.warning(f"⚠️ No jobs found in BigQuery for {role_name}. Consider running ETL pipeline to populate data.")
        else:
            logger.info(f"✅ Found {len(jobs)} jobs for {role_name}")
        
        return jobs
    
    def get_training_data(self) -> pd.DataFrame:
        """Get training data from BigQuery raw_jobs table for model retraining"""
        try:
            query = f"""
            SELECT 
                CAST(title AS STRING) as title,
                CASE 
                    WHEN company LIKE '%display_name%' THEN 
                        REGEXP_EXTRACT(company, r"'display_name':\\s*'([^']+)'")
                    ELSE CAST(company AS STRING)
                END as company,
                CASE 
                    WHEN location LIKE '%display_name%' THEN 
                        REGEXP_EXTRACT(location, r"'display_name':\\s*'([^']+)'")
                    ELSE CAST(location AS STRING)
                END as location,
                CAST(requirements AS STRING) as requirements,
                CAST(salary_min AS FLOAT64) as salary_min,
                CAST(salary_max AS FLOAT64) as salary_max,
                CAST(description AS STRING) as description,
                'adzuna' as source
            FROM `{self.project_id}.runagen_bronze.raw_jobs`
            WHERE title IS NOT NULL
            LIMIT 5000
            """
            
            df = self.bq_client.query(query).to_dataframe()
            
            if not df.empty:
                # Post-process columns
                df['skills'] = df['requirements'].apply(
                    lambda x: [s.strip() for s in str(x).split(',') if s.strip()] if x else []
                )
                df['skills_count'] = df['skills'].apply(len)
                df['description_length'] = df['description'].fillna('').apply(len)
                df['has_salary'] = df['salary_min'].apply(lambda x: 1 if pd.notna(x) and x > 0 else 0)
                df['job_type'] = 'full_time'
                df['experience_required'] = ''
                
                # Normalize career
                df['career'] = df['title'].apply(self._normalize_role_title)
                # Fill missing careers with a default mapping or software engineer
                df['career'] = df['career'].fillna('Software Engineer')
                
                # Keep only training columns
                cols = [
                    'title', 'company', 'location', 'skills', 'experience_required',
                    'salary_min', 'salary_max', 'job_type', 'description_length',
                    'skills_count', 'has_salary', 'source', 'career'
                ]
                df = df[cols]
                
            return df
            
        except Exception as e:
            logger.error(f"Error getting training data from BigQuery: {e}")
            return pd.DataFrame()

    def close(self):
        """Close BigQuery connection"""
        if self.bq_client:
            self.bq_client.close()


# Global instance
_data_provider = None

def get_data_provider():
    """Get or create global data provider instance"""
    global _data_provider
    if _data_provider is None:
        _data_provider = BigQueryDataProvider()
    return _data_provider
