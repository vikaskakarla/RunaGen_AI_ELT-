"""
ETL Pipeline: MongoDB → BigQuery
Extract data from MongoDB and load into BigQuery data warehouse
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from pymongo import MongoClient
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd
from datetime import datetime
from typing import List, Dict
import logging
import warnings

# Suppress warnings from BigQuery library
warnings.filterwarnings('ignore', category=FutureWarning, module='google.cloud.bigquery._pandas_helpers')
warnings.filterwarnings('ignore', category=UserWarning, module='google.cloud.bigquery._pandas_helpers')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MongoDBToBigQueryETL:
    def __init__(self):
        # MongoDB connection - use MONGO_URI from .env
        mongo_uri = os.getenv('MONGO_URI', os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'))
        self.mongo_client = MongoClient(mongo_uri)
        
        # Get database name from URI or use default
        mongo_db = os.getenv('MONGO_DB', os.getenv('MONGODB_DB', 'runagen_db'))
        self.mongo_db = self.mongo_client[mongo_db]
        
        # BigQuery connection
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'credentials/bigquery-key.json')
        gcp_json = os.getenv('GCP_SERVICE_ACCOUNT_JSON')
        
        if gcp_json:
            try:
                import json
                info = json.loads(gcp_json)
                credentials = service_account.Credentials.from_service_account_info(info)
                self.bq_client = bigquery.Client(
                    credentials=credentials,
                    project=os.getenv('GCP_PROJECT_ID', 'runagen-ai-warehouse')
                )
                logger.info("✓ BigQuery client initialized from GCP_SERVICE_ACCOUNT_JSON")
            except Exception as e:
                logger.error(f"Failed to initialize BigQuery from GCP_SERVICE_ACCOUNT_JSON: {e}")
                self.bq_client = bigquery.Client(project=os.getenv('GCP_PROJECT_ID', 'runagen-ai-warehouse'))
        elif os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.bq_client = bigquery.Client(
                credentials=credentials,
                project=os.getenv('GCP_PROJECT_ID', 'runagen-ai-warehouse')
            )
        else:
            logger.warning("⚠️  BigQuery credentials not found. Using default credentials.")
            self.bq_client = bigquery.Client(project=os.getenv('GCP_PROJECT_ID', 'runagen-ai-warehouse'))
        
        self.project_id = os.getenv('GCP_PROJECT_ID', 'runagen-ai-warehouse')
        self.dataset_bronze = 'runagen_bronze'
        self.dataset_silver = 'runagen_silver'
        self.dataset_gold = 'runagen_gold'
    
    def _extract_skills_from_text(self, text: str) -> str:
        """Extract common skills from job description text"""
        if not text or not isinstance(text, str):
            return ''
        
        # Common tech skills to look for
        common_skills = [
            'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Ruby', 'PHP', 'Go', 'Rust',
            'React', 'Angular', 'Vue', 'Node.js', 'Django', 'Flask', 'Spring', 'Express',
            'SQL', 'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Cassandra', 'Oracle',
            'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins', 'Git', 'CI/CD',
            'Machine Learning', 'Deep Learning', 'TensorFlow', 'PyTorch', 'Scikit-learn',
            'REST API', 'GraphQL', 'Microservices', 'Agile', 'Scrum', 'DevOps',
            'HTML', 'CSS', 'Bootstrap', 'Tailwind', 'SASS', 'LESS',
            'Linux', 'Unix', 'Windows', 'Mac OS',
            'Pandas', 'NumPy', 'Matplotlib', 'Seaborn',
            'Spark', 'Hadoop', 'Kafka', 'Airflow', 'dbt',
            'Tableau', 'Power BI', 'Looker', 'Excel',
            '.NET', 'ASP.NET', 'Entity Framework',
            'Android', 'iOS', 'React Native', 'Flutter',
            'Selenium', 'Pytest', 'JUnit', 'Jest', 'Mocha'
        ]
        
        text_lower = text.lower()
        found_skills = []
        
        for skill in common_skills:
            if skill.lower() in text_lower:
                found_skills.append(skill)
        
        return ', '.join(found_skills) if found_skills else ''
    
    def extract_jobs_from_mongodb(self) -> pd.DataFrame:
        """Extract job data from MongoDB"""
        logger.info("📥 Extracting jobs from MongoDB...")
        
        try:
            # Try different collection names
            collection_names = ['bronze_jobs', 'jobs', 'silver_jobs']
            jobs_collection = None
            collection_name_used = None
            
            for coll_name in collection_names:
                if coll_name in self.mongo_db.list_collection_names():
                    jobs_collection = self.mongo_db[coll_name]
                    collection_name_used = coll_name
                    break
            
            if collection_name_used is None:
                logger.warning("⚠️  No jobs collection found in MongoDB")
                return pd.DataFrame()
            
            logger.info(f"   Using collection: {collection_name_used}")
            
            # Get total count
            total_count = jobs_collection.count_documents({})
            logger.info(f"   Total jobs in MongoDB: {total_count:,}")
            
            # Process in batches to avoid memory issues
            batch_size = 5000
            all_jobs = []
            
            for skip in range(0, total_count, batch_size):
                logger.info(f"   Processing batch {skip//batch_size + 1} ({skip:,} to {min(skip+batch_size, total_count):,})...")
                batch = list(jobs_collection.find().skip(skip).limit(batch_size))
                all_jobs.extend(batch)
            
            jobs = all_jobs
            logger.info(f"   Loaded {len(jobs):,} jobs from MongoDB")
            
            if not jobs:
                logger.warning("⚠️  No jobs found in MongoDB")
                return pd.DataFrame()
            
            # Extract data from nested structure
            extracted_jobs = []
            for job in jobs:
                try:
                    # Data is nested under 'data' key
                    if 'data' in job and isinstance(job['data'], dict):
                        data = job['data']
                        
                        # Extract company name from nested object
                        company = ''
                        if 'company' in data and isinstance(data['company'], dict):
                            company = data['company'].get('display_name', '')
                        elif 'company' in data:
                            company = str(data['company'])
                        
                        # Extract location from nested object
                        location = ''
                        if 'location' in data and isinstance(data['location'], dict):
                            location = data['location'].get('display_name', '')
                        elif 'location' in data:
                            location = str(data['location'])
                        
                        # Extract category
                        category = ''
                        if 'category' in data and isinstance(data['category'], dict):
                            category = data['category'].get('label', '')
                        
                        # Build flat job record
                        job_record = {
                            'job_id': str(job.get('_id', '')),
                            'external_id': data.get('id', ''),
                            'title': data.get('title', ''),
                            'company': company,
                            'location': location,
                            'description': data.get('description', ''),
                            'url': data.get('redirect_url', ''),
                            'posted_date': data.get('created', None),
                            'category': category,
                            'latitude': data.get('latitude', None),
                            'longitude': data.get('longitude', None),
                            'salary_is_predicted': data.get('salary_is_predicted', '0'),
                            # Salary fields don't exist in Adzuna data
                            'salary_min': data.get('salary_min', None),
                            'salary_max': data.get('salary_max', None),
                            'currency': data.get('currency', 'INR'),
                            # Metadata
                            'source': job.get('metadata', {}).get('source', 'adzuna'),
                            'inserted_at': job.get('inserted_at', None),
                            'layer': job.get('layer', 'bronze')
                        }
                        
                        extracted_jobs.append(job_record)
                    else:
                        # Fallback for non-nested structure
                        extracted_jobs.append(job)
                except Exception as e:
                    logger.warning(f"⚠️ Error extracting job {job.get('_id')}: {e}")
                    continue
            
            # Convert to DataFrame
            df = pd.DataFrame(extracted_jobs)
            
            if df.empty:
                logger.warning("⚠️ No jobs extracted")
                return pd.DataFrame()
            
            # Add scraped_at timestamp
            df['scraped_at'] = datetime.now()
            
            # Extract requirements from description (since Adzuna doesn't provide them)
            logger.info("   Extracting skills/requirements from descriptions...")
            df['requirements'] = df['description'].apply(self._extract_skills_from_text)
            
            # Ensure required columns exist
            required_columns = [
                'job_id', 'external_id', 'source', 'title', 'company', 'location', 
                'description', 'requirements', 'salary_min', 'salary_max', 
                'currency', 'category', 'posted_date', 'scraped_at', 'url'
            ]
            
            for col in required_columns:
                if col not in df.columns:
                    df[col] = None
            
            # Cast columns to proper types
            df['job_id'] = df['job_id'].astype(str)
            df['external_id'] = df['external_id'].fillna('').astype(str)
            df['source'] = df['source'].fillna('adzuna').astype(str)
            df['title'] = df['title'].fillna('').astype(str)
            df['company'] = df['company'].fillna('').astype(str)
            df['location'] = df['location'].fillna('').astype(str)
            df['description'] = df['description'].fillna('').astype(str)
            df['requirements'] = df['requirements'].fillna('').astype(str)
            df['currency'] = df['currency'].fillna('INR').astype(str)
            df['category'] = df['category'].fillna('').astype(str)
            df['url'] = df['url'].fillna('').astype(str)
            
            # Convert salary columns to float
            df['salary_min'] = pd.to_numeric(df['salary_min'], errors='coerce')
            df['salary_max'] = pd.to_numeric(df['salary_max'], errors='coerce')
            
            # Select only required columns
            df = df[required_columns]
            
            logger.info(f"✅ Extracted {len(df)} jobs from MongoDB")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error extracting jobs: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def extract_skills_from_mongodb(self) -> pd.DataFrame:
        """Extract skills data from MongoDB"""
        logger.info("📥 Extracting skills from MongoDB...")
        
        try:
            # Try different collection names
            collection_names = ['bronze_skills', 'skills', 'silver_skills']
            skills_collection = None
            collection_name_used = None
            
            for coll_name in collection_names:
                if coll_name in self.mongo_db.list_collection_names():
                    skills_collection = self.mongo_db[coll_name]
                    collection_name_used = coll_name
                    break
            
            if collection_name_used is None:
                logger.warning("⚠️  No skills collection found in MongoDB")
                return pd.DataFrame()
            
            logger.info(f"   Using collection: {collection_name_used}")
            skills = list(skills_collection.find())
            
            if not skills:
                logger.warning("⚠️  No skills found in MongoDB")
                return pd.DataFrame()
            
            # Extract data from nested structure
            extracted_skills = []
            for skill in skills:
                try:
                    # Data is nested under 'data' key
                    if 'data' in skill and isinstance(skill['data'], dict):
                        data = skill['data']
                        
                        skill_record = {
                            'skill_id': str(skill.get('_id', '')),
                            'external_id': data.get('id', ''),
                            'skill_name': data.get('name', ''),
                            'skill_category': data.get('category', ''),
                            'source': skill.get('metadata', {}).get('source', 'esco'),
                            'inserted_at': skill.get('inserted_at', None),
                            'layer': skill.get('layer', 'bronze')
                        }
                        
                        extracted_skills.append(skill_record)
                    else:
                        # Fallback for non-nested structure
                        extracted_skills.append(skill)
                except Exception as e:
                    logger.warning(f"⚠️ Error extracting skill {skill.get('_id')}: {e}")
                    continue
            
            # Convert to DataFrame
            df = pd.DataFrame(extracted_skills)
            
            if df.empty:
                logger.warning("⚠️ No skills extracted")
                return pd.DataFrame()
            
            # Add extracted_at timestamp
            df['extracted_at'] = datetime.now()
            
            # Ensure required columns
            required_columns = ['skill_id', 'external_id', 'skill_name', 'skill_category', 'source', 'extracted_at']
            
            for col in required_columns:
                if col not in df.columns:
                    df[col] = None
            
            # Cast columns to proper types
            df['skill_id'] = df['skill_id'].astype(str)
            df['external_id'] = df['external_id'].fillna('').astype(str)
            df['skill_name'] = df['skill_name'].fillna('').astype(str)
            df['skill_category'] = df['skill_category'].fillna('Other').astype(str)
            df['source'] = df['source'].fillna('esco').astype(str)
            
            # Select only required columns
            df = df[required_columns]
            
            logger.info(f"✅ Extracted {len(df)} skills from MongoDB")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error extracting skills: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def extract_resumes_from_mongodb(self) -> pd.DataFrame:
        """Extract resume data from MongoDB (if stored)"""
        logger.info("📥 Extracting resumes from MongoDB...")
        
        try:
            # Check if resumes collection exists
            if 'resumes' not in self.mongo_db.list_collection_names():
                logger.info("ℹ️  No resumes collection found in MongoDB")
                return pd.DataFrame()
            
            resumes_collection = self.mongo_db['resumes']
            resumes = list(resumes_collection.find())
            
            if not resumes:
                logger.warning("⚠️  No resumes found in MongoDB")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(resumes)
            
            # Rename _id to resume_id
            if '_id' in df.columns:
                df['resume_id'] = df['_id'].astype(str)
                df = df.drop('_id', axis=1)
            
            # Add metadata
            df['uploaded_at'] = datetime.now()
            df['processing_status'] = 'pending'
            
            # Ensure required columns
            required_columns = [
                'resume_id', 'user_id', 'raw_text', 'file_name', 
                'file_size', 'uploaded_at', 'processing_status'
            ]
            
            for col in required_columns:
                if col not in df.columns:
                    df[col] = None
            
            df = df[required_columns]
            
            logger.info(f"✅ Extracted {len(df)} resumes from MongoDB")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error extracting resumes: {e}")
            return pd.DataFrame()
    
    def load_to_bigquery(self, df: pd.DataFrame, table_name: str, dataset: str = None):
        """Load DataFrame to BigQuery with explicit schema in batches"""
        if df.empty:
            logger.warning(f"⚠️  No data to load for {table_name}")
            return
        
        dataset = dataset or self.dataset_bronze
        table_id = f"{self.project_id}.{dataset}.{table_name}"
        
        # Define explicit schemas
        schema = None
        
        if table_name == 'raw_jobs':
            schema = [
                bigquery.SchemaField("job_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("external_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("source", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("title", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("company", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("location", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("requirements", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("salary_min", "FLOAT64", mode="NULLABLE"),
                bigquery.SchemaField("salary_max", "FLOAT64", mode="NULLABLE"),
                bigquery.SchemaField("currency", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("category", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("posted_date", "TIMESTAMP", mode="NULLABLE"),
                bigquery.SchemaField("scraped_at", "TIMESTAMP", mode="NULLABLE"),
                bigquery.SchemaField("url", "STRING", mode="NULLABLE"),
            ]
        
        elif table_name == 'raw_skills':
            schema = [
                bigquery.SchemaField("skill_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("external_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("skill_name", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("skill_category", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("source", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("extracted_at", "TIMESTAMP", mode="NULLABLE"),
            ]
        
        elif table_name == 'raw_resumes':
            schema = [
                bigquery.SchemaField("resume_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("user_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("raw_text", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("file_name", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("file_size", "INTEGER", mode="NULLABLE"),
                bigquery.SchemaField("uploaded_at", "TIMESTAMP", mode="NULLABLE"),
                bigquery.SchemaField("processing_status", "STRING", mode="NULLABLE"),
            ]
        
        # Load in batches for large datasets
        batch_size = 5000
        total_rows = len(df)
        
        if total_rows > batch_size:
            logger.info(f"📤 Loading {total_rows:,} rows to {table_id} in batches...")
            
            for i in range(0, total_rows, batch_size):
                batch_df = df.iloc[i:i+batch_size]
                batch_num = i // batch_size + 1
                total_batches = (total_rows + batch_size - 1) // batch_size
                
                logger.info(f"   Batch {batch_num}/{total_batches}: Loading {len(batch_df):,} rows...")
                
                # First batch: WRITE_TRUNCATE, rest: WRITE_APPEND
                write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE if i == 0 else bigquery.WriteDisposition.WRITE_APPEND
                
                job_config = bigquery.LoadJobConfig(
                    write_disposition=write_disposition,
                    schema=schema,
                )
                
                try:
                    job = self.bq_client.load_table_from_dataframe(
                        batch_df, table_id, job_config=job_config
                    )
                    job.result()  # Wait for completion
                    logger.info(f"   ✅ Batch {batch_num} loaded successfully")
                except Exception as e:
                    logger.error(f"   ❌ Error loading batch {batch_num}: {e}")
                    raise
            
            logger.info(f"✅ Loaded all {total_rows:,} rows to {table_id}")
        else:
            # Small dataset, load all at once
            logger.info(f"📤 Loading {total_rows:,} rows to {table_id}...")
            
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                schema=schema,
            )
            
            try:
                job = self.bq_client.load_table_from_dataframe(
                    df, table_id, job_config=job_config
                )
                job.result()
                logger.info(f"✅ Loaded {total_rows:,} rows to {table_id}")
            except Exception as e:
                logger.error(f"❌ Error loading to BigQuery: {e}")
                raise
    
    def run_full_etl(self):
        """Run complete ETL pipeline"""
        logger.info("🚀 Starting MongoDB → BigQuery ETL Pipeline...")
        logger.info("="*70)
        
        start_time = datetime.now()
        
        # Extract from MongoDB
        logger.info("\n📥 EXTRACTION PHASE")
        logger.info("-"*70)
        
        jobs_df = self.extract_jobs_from_mongodb()
        skills_df = self.extract_skills_from_mongodb()
        resumes_df = self.extract_resumes_from_mongodb()
        
        # Load to BigQuery (Bronze layer)
        logger.info("\n📤 LOADING PHASE (Bronze Layer)")
        logger.info("-"*70)
        
        if not jobs_df.empty:
            self.load_to_bigquery(jobs_df, 'raw_jobs', self.dataset_bronze)
        
        if not skills_df.empty:
            self.load_to_bigquery(skills_df, 'raw_skills', self.dataset_bronze)
        
        if not resumes_df.empty:
            self.load_to_bigquery(resumes_df, 'raw_resumes', self.dataset_bronze)
        
        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("\n" + "="*70)
        logger.info("✅ ETL PIPELINE COMPLETE!")
        logger.info("="*70)
        logger.info(f"📊 Summary:")
        logger.info(f"  - Jobs extracted: {len(jobs_df)}")
        logger.info(f"  - Skills extracted: {len(skills_df)}")
        logger.info(f"  - Resumes extracted: {len(resumes_df)}")
        logger.info(f"  - Duration: {duration:.2f} seconds")
        logger.info(f"  - Destination: {self.project_id}.{self.dataset_bronze}")
        logger.info("="*70)
        
        return {
            'jobs_count': len(jobs_df),
            'skills_count': len(skills_df),
            'resumes_count': len(resumes_df),
            'duration_seconds': duration,
            'status': 'success'
        }
    
    def run_incremental_load(self, collection_name: str, last_sync_time: datetime = None):
        """Run incremental load for a specific collection"""
        logger.info(f"🔄 Running incremental load for {collection_name}...")
        
        collection = self.mongo_db[collection_name]
        
        # Query for new/updated records
        query = {}
        if last_sync_time:
            query = {'updated_at': {'$gt': last_sync_time}}
        
        records = list(collection.find(query))
        
        if not records:
            logger.info(f"ℹ️  No new records found for {collection_name}")
            return
        
        df = pd.DataFrame(records)
        
        # Convert _id to string
        if '_id' in df.columns:
            df['id'] = df['_id'].astype(str)
            df = df.drop('_id', axis=1)
        
        # Load to BigQuery
        table_name = f"raw_{collection_name}"
        self.load_to_bigquery(df, table_name, self.dataset_bronze)
        
        logger.info(f"✅ Incremental load complete: {len(df)} records")
    
    def get_mongodb_stats(self) -> Dict:
        """Get statistics from MongoDB"""
        stats = {}
        
        # Try different collection name patterns
        collection_patterns = {
            'jobs': ['bronze_jobs', 'jobs', 'silver_jobs'],
            'skills': ['bronze_skills', 'skills', 'silver_skills'],
            'resumes': ['resumes']
        }
        
        for key, patterns in collection_patterns.items():
            count = 0
            for pattern in patterns:
                if pattern in self.mongo_db.list_collection_names():
                    count = self.mongo_db[pattern].count_documents({})
                    break
            stats[key] = count
        
        return stats
    
    def extract_live_jobs_from_mongodb(self) -> pd.DataFrame:
        """Extract live jobs from MongoDB (from live_jobs collection)"""
        logger.info("📥 Extracting live jobs from MongoDB...")
        
        try:
            # Check if live_jobs collection exists
            if 'live_jobs' not in self.mongo_db.list_collection_names():
                logger.info("ℹ️  No live_jobs collection found in MongoDB")
                return pd.DataFrame()
            
            collection = self.mongo_db['live_jobs']
            
            # Get jobs from last 7 days
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=7)
            cursor = collection.find({
                'ingested_at': {'$gte': cutoff_date},
                'is_active': True
            })
            
            jobs_data = []
            for doc in cursor:
                # Convert MongoDB document to flat structure
                job_data = {
                    'job_id': str(doc.get('_id', '')),
                    'external_id': doc.get('source_id', ''),
                    'source': doc.get('source', 'live_api'),
                    'title': doc.get('title', ''),
                    'company': doc.get('company', ''),
                    'location': doc.get('location', ''),
                    'description': doc.get('description', ''),
                    'requirements': ', '.join(doc.get('skills', [])),  # Convert skills list to string
                    'salary_min': doc.get('salary_min'),
                    'salary_max': doc.get('salary_max'),
                    'currency': doc.get('currency', 'INR'),
                    'category': self._categorize_job_title(doc.get('title', '')),
                    'posted_date': doc.get('posted_date'),
                    'scraped_at': doc.get('ingested_at', datetime.now()),
                    'url': doc.get('url', ''),
                    'job_type': doc.get('job_type', 'full_time'),
                    'experience_level': doc.get('experience_required', ''),
                    'is_live': True  # Mark as live data
                }
                jobs_data.append(job_data)
            
            df = pd.DataFrame(jobs_data)
            
            if df.empty:
                logger.info("ℹ️  No live jobs found")
                return pd.DataFrame()
            
            # Ensure required columns exist and have proper types
            required_columns = [
                'job_id', 'external_id', 'source', 'title', 'company', 'location', 
                'description', 'requirements', 'salary_min', 'salary_max', 
                'currency', 'category', 'posted_date', 'scraped_at', 'url'
            ]
            
            for col in required_columns:
                if col not in df.columns:
                    df[col] = None
            
            # Cast columns to proper types
            df['job_id'] = df['job_id'].astype(str)
            df['external_id'] = df['external_id'].fillna('').astype(str)
            df['source'] = df['source'].fillna('live_api').astype(str)
            df['title'] = df['title'].fillna('').astype(str)
            df['company'] = df['company'].fillna('').astype(str)
            df['location'] = df['location'].fillna('').astype(str)
            df['description'] = df['description'].fillna('').astype(str)
            df['requirements'] = df['requirements'].fillna('').astype(str)
            df['currency'] = df['currency'].fillna('INR').astype(str)
            df['category'] = df['category'].fillna('').astype(str)
            df['url'] = df['url'].fillna('').astype(str)
            
            # Convert salary columns to float
            df['salary_min'] = pd.to_numeric(df['salary_min'], errors='coerce')
            df['salary_max'] = pd.to_numeric(df['salary_max'], errors='coerce')
            
            # Select only required columns
            df = df[required_columns]
            
            logger.info(f"✅ Extracted {len(df)} live jobs from MongoDB")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error extracting live jobs from MongoDB: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def extract_live_skills_from_mongodb(self) -> pd.DataFrame:
        """Extract live skills from MongoDB (from live_skills collection)"""
        logger.info("📥 Extracting live skills from MongoDB...")
        
        try:
            # Check if live_skills collection exists
            if 'live_skills' not in self.mongo_db.list_collection_names():
                logger.info("ℹ️  No live_skills collection found in MongoDB")
                return pd.DataFrame()
            
            collection = self.mongo_db['live_skills']
            
            # Get recent skills data
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=7)
            cursor = collection.find({
                'last_seen': {'$gte': cutoff_date}
            })
            
            skills_data = []
            for doc in cursor:
                skill_data = {
                    'skill_id': str(doc.get('_id', '')),
                    'external_id': str(doc.get('_id', '')),  # Use MongoDB ID as external ID
                    'skill_name': doc.get('skill_name', ''),
                    'skill_category': self._categorize_skill(doc.get('skill_name', '')),
                    'source': doc.get('source', 'live_jobs'),
                    'extracted_at': doc.get('last_seen', datetime.now()),
                    'demand_count': doc.get('demand_count', 0),
                    'total_mentions': doc.get('total_mentions', 0),
                    'is_trending': doc.get('is_trending', False),
                    'is_live': True  # Mark as live data
                }
                skills_data.append(skill_data)
            
            df = pd.DataFrame(skills_data)
            
            if df.empty:
                logger.info("ℹ️  No live skills found")
                return pd.DataFrame()
            
            # Ensure required columns exist
            required_columns = ['skill_id', 'external_id', 'skill_name', 'skill_category', 'source', 'extracted_at']
            
            for col in required_columns:
                if col not in df.columns:
                    df[col] = None
            
            # Cast columns to proper types
            df['skill_id'] = df['skill_id'].astype(str)
            df['external_id'] = df['external_id'].fillna('').astype(str)
            df['skill_name'] = df['skill_name'].fillna('').astype(str)
            df['skill_category'] = df['skill_category'].fillna('Other').astype(str)
            df['source'] = df['source'].fillna('live_jobs').astype(str)
            
            # Select only required columns
            df = df[required_columns]
            
            logger.info(f"✅ Extracted {len(df)} live skills from MongoDB")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error extracting live skills from MongoDB: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def _categorize_skill(self, skill_name: str) -> str:
        """Categorize skill based on name"""
        if not skill_name:
            return 'Other'
        
        skill_lower = skill_name.lower()
        
        if any(lang in skill_lower for lang in ['python', 'java', 'javascript', 'c++', 'c#', 'go', 'rust']):
            return 'Programming Language'
        elif any(fw in skill_lower for fw in ['react', 'angular', 'vue', 'django', 'flask', 'spring']):
            return 'Framework'
        elif any(db in skill_lower for db in ['sql', 'mysql', 'postgresql', 'mongodb', 'redis']):
            return 'Database'
        elif any(cloud in skill_lower for cloud in ['aws', 'azure', 'gcp', 'docker', 'kubernetes']):
            return 'Cloud/DevOps'
        elif any(ml in skill_lower for ml in ['machine learning', 'data science', 'tensorflow', 'pytorch']):
            return 'AI/ML'
        else:
            return 'Other'
    
    def _categorize_job_title(self, title: str) -> str:
        """Categorize job based on title"""
        if not title:
            return 'Other'
        
        title_lower = title.lower()
        
        if any(term in title_lower for term in ['software engineer', 'developer', 'programmer']):
            return 'Software Development'
        elif any(term in title_lower for term in ['data scientist', 'data analyst', 'data engineer']):
            return 'Data Science'
        elif any(term in title_lower for term in ['product manager', 'project manager']):
            return 'Management'
        elif any(term in title_lower for term in ['designer', 'ui', 'ux']):
            return 'Design'
        elif any(term in title_lower for term in ['devops', 'sre', 'infrastructure']):
            return 'DevOps'
        else:
            return 'Other'
    
    def get_bigquery_stats(self) -> Dict:
        """Get statistics from BigQuery"""
        stats = {}
        
        for table_name in ['raw_jobs', 'raw_skills', 'raw_resumes', 'raw_jobs_live', 'raw_skills_live']:
            try:
                table_id = f"{self.project_id}.{self.dataset_bronze}.{table_name}"
                table = self.bq_client.get_table(table_id)
                stats[table_name] = table.num_rows
            except Exception:
                stats[table_name] = 0
        
        return stats


def main():
    """Main ETL execution"""
    print("\n" + "="*70)
    print("🚀 MongoDB → BigQuery ETL Pipeline")
    print("="*70 + "\n")
    
    # Initialize ETL
    etl = MongoDBToBigQueryETL()
    
    # Show MongoDB stats
    print("📊 MongoDB Statistics:")
    mongo_stats = etl.get_mongodb_stats()
    for collection, count in mongo_stats.items():
        print(f"  - {collection}: {count:,} records")
    print()
    
    # Run ETL
    result = etl.run_full_etl()
    
    # Show BigQuery stats
    print("\n📊 BigQuery Statistics:")
    bq_stats = etl.get_bigquery_stats()
    for table, count in bq_stats.items():
        print(f"  - {table}: {count:,} rows")
    
    print("\n✅ Pipeline execution complete!")
    print("="*70 + "\n")
    
    return result


if __name__ == "__main__":
    main()
