"""
Reset BigQuery Tables - Delete old data and recreate with correct schema
"""
import os
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account

load_dotenv()

# BigQuery connection
credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'credentials/bigquery-key.json')

if os.path.exists(credentials_path):
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    bq_client = bigquery.Client(
        credentials=credentials,
        project=os.getenv('GCP_PROJECT_ID', 'runagen-ai')
    )
else:
    bq_client = bigquery.Client(project=os.getenv('GCP_PROJECT_ID', 'runagen-ai'))

project_id = os.getenv('GCP_PROJECT_ID', 'runagen-ai')
dataset = 'runagen_bronze'

print("="*70)
print("🗑️  RESET BIGQUERY TABLES")
print("="*70)
print(f"\nProject: {project_id}")
print(f"Dataset: {dataset}")

# Tables to reset
tables_to_reset = ['raw_jobs', 'raw_skills']

print("\n⚠️  WARNING: This will DELETE all data in the following tables:")
for table in tables_to_reset:
    print(f"   - {dataset}.{table}")

print("\nAre you sure you want to continue? (yes/no): ", end='')
# For automation, we'll proceed automatically
print("yes (automated)")

print("\n🗑️  Deleting old tables...")

for table_name in tables_to_reset:
    table_id = f"{project_id}.{dataset}.{table_name}"
    
    try:
        # Delete table if exists
        bq_client.delete_table(table_id, not_found_ok=True)
        print(f"   ✅ Deleted {table_name}")
    except Exception as e:
        print(f"   ⚠️  Error deleting {table_name}: {e}")

print("\n📋 Creating tables with correct schema...")

# Create raw_jobs table with correct schema
jobs_schema = [
    bigquery.SchemaField("job_id", "STRING", mode="REQUIRED", description="Unique job identifier"),
    bigquery.SchemaField("external_id", "STRING", mode="NULLABLE", description="External API job ID"),
    bigquery.SchemaField("source", "STRING", mode="NULLABLE", description="Data source (adzuna, linkedin, etc)"),
    bigquery.SchemaField("title", "STRING", mode="NULLABLE", description="Job title"),
    bigquery.SchemaField("company", "STRING", mode="NULLABLE", description="Company name"),
    bigquery.SchemaField("location", "STRING", mode="NULLABLE", description="Job location"),
    bigquery.SchemaField("description", "STRING", mode="NULLABLE", description="Full job description"),
    bigquery.SchemaField("requirements", "STRING", mode="NULLABLE", description="Extracted skills/requirements"),
    bigquery.SchemaField("salary_min", "FLOAT64", mode="NULLABLE", description="Minimum salary"),
    bigquery.SchemaField("salary_max", "FLOAT64", mode="NULLABLE", description="Maximum salary"),
    bigquery.SchemaField("currency", "STRING", mode="NULLABLE", description="Salary currency"),
    bigquery.SchemaField("category", "STRING", mode="NULLABLE", description="Job category"),
    bigquery.SchemaField("posted_date", "TIMESTAMP", mode="NULLABLE", description="Job posting date"),
    bigquery.SchemaField("scraped_at", "TIMESTAMP", mode="NULLABLE", description="Data collection timestamp"),
    bigquery.SchemaField("url", "STRING", mode="NULLABLE", description="Job posting URL"),
]

jobs_table = bigquery.Table(f"{project_id}.{dataset}.raw_jobs", schema=jobs_schema)
jobs_table.description = "Raw job postings from various sources (Adzuna, LinkedIn, etc)"

try:
    jobs_table = bq_client.create_table(jobs_table)
    print(f"   ✅ Created raw_jobs table with {len(jobs_schema)} columns")
except Exception as e:
    print(f"   ❌ Error creating raw_jobs: {e}")

# Create raw_skills table with correct schema
skills_schema = [
    bigquery.SchemaField("skill_id", "STRING", mode="REQUIRED", description="Unique skill identifier"),
    bigquery.SchemaField("external_id", "STRING", mode="NULLABLE", description="External skill ID"),
    bigquery.SchemaField("skill_name", "STRING", mode="NULLABLE", description="Skill name"),
    bigquery.SchemaField("skill_category", "STRING", mode="NULLABLE", description="Skill category"),
    bigquery.SchemaField("source", "STRING", mode="NULLABLE", description="Data source (esco, custom, etc)"),
    bigquery.SchemaField("extracted_at", "TIMESTAMP", mode="NULLABLE", description="Extraction timestamp"),
]

skills_table = bigquery.Table(f"{project_id}.{dataset}.raw_skills", schema=skills_schema)
skills_table.description = "Master skills taxonomy from ESCO and other sources"

try:
    skills_table = bq_client.create_table(skills_table)
    print(f"   ✅ Created raw_skills table with {len(skills_schema)} columns")
except Exception as e:
    print(f"   ❌ Error creating raw_skills: {e}")

print("\n" + "="*70)
print("✅ RESET COMPLETE!")
print("="*70)
print("\nNext steps:")
print("1. Run ETL to load data: python3 run_etl.py")
print("2. Verify data in BigQuery console")
print("3. Run data quality checker: python3 src/preprocessing/bigquery_data_cleaner.py")
print("="*70)
