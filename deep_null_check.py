"""
Deep NULL value check across all BigQuery tables
Checks every field for NULL, empty strings, and zero values
"""
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd

load_dotenv()

def deep_null_check():
    """Comprehensive NULL check for all tables"""
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'credentials/bigquery-key.json')
    
    if os.path.exists(credentials_path):
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        client = bigquery.Client(
            credentials=credentials,
            project=os.getenv('GCP_PROJECT_ID', 'runagen-ai')
        )
    else:
        client = bigquery.Client(project=os.getenv('GCP_PROJECT_ID', 'runagen-ai'))
    
    project_id = os.getenv('GCP_PROJECT_ID', 'runagen-ai')
    dataset = 'runagen_bronze'
    
    print("="*80)
    print("🔍 DEEP NULL VALUE ANALYSIS")
    print("="*80)
    
    # Check raw_jobs table
    print("\n📊 TABLE: raw_jobs")
    print("-"*80)
    
    jobs_query = f"""
    SELECT 
        COUNT(*) as total_rows,
        
        -- String fields
        COUNTIF(job_id IS NULL OR job_id = '') as null_job_id,
        COUNTIF(external_id IS NULL OR external_id = '') as null_external_id,
        COUNTIF(source IS NULL OR source = '') as null_source,
        COUNTIF(title IS NULL OR title = '') as null_title,
        COUNTIF(company IS NULL OR company = '') as null_company,
        COUNTIF(location IS NULL OR location = '') as null_location,
        COUNTIF(description IS NULL OR description = '') as null_description,
        COUNTIF(requirements IS NULL OR requirements = '') as null_requirements,
        COUNTIF(currency IS NULL OR currency = '') as null_currency,
        COUNTIF(category IS NULL OR category = '') as null_category,
        COUNTIF(url IS NULL OR url = '') as null_url,
        
        -- Numeric fields
        COUNTIF(salary_min IS NULL) as null_salary_min,
        COUNTIF(salary_max IS NULL) as null_salary_max,
        COUNTIF(salary_min = 0) as zero_salary_min,
        COUNTIF(salary_max = 0) as zero_salary_max,
        
        -- Timestamp fields
        COUNTIF(posted_date IS NULL) as null_posted_date,
        COUNTIF(scraped_at IS NULL) as null_scraped_at
        
    FROM `{project_id}.{dataset}.raw_jobs`
    """
    
    try:
        df = client.query(jobs_query).to_dataframe()
        
        if not df.empty:
            row = df.iloc[0]
            total = int(row['total_rows'])
            
            print(f"Total Rows: {total:,}\n")
            
            # Analyze each field
            fields = [
                ('job_id', 'null_job_id'),
                ('external_id', 'null_external_id'),
                ('source', 'null_source'),
                ('title', 'null_title'),
                ('company', 'null_company'),
                ('location', 'null_location'),
                ('description', 'null_description'),
                ('requirements', 'null_requirements'),
                ('currency', 'null_currency'),
                ('category', 'null_category'),
                ('url', 'null_url'),
                ('posted_date', 'null_posted_date'),
                ('scraped_at', 'null_scraped_at'),
            ]
            
            print("String/Timestamp Fields:")
            for field_name, col_name in fields:
                null_count = int(row[col_name])
                pct = (null_count / total * 100) if total > 0 else 0
                status = "✅" if pct == 0 else "⚠️" if pct < 10 else "❌"
                print(f"  {status} {field_name:20s}: {null_count:6,} null ({pct:5.2f}%)")
            
            print("\nNumeric Fields (Salary):")
            salary_fields = [
                ('salary_min (NULL)', 'null_salary_min'),
                ('salary_min (ZERO)', 'zero_salary_min'),
                ('salary_max (NULL)', 'null_salary_max'),
                ('salary_max (ZERO)', 'zero_salary_max'),
            ]
            
            for field_name, col_name in salary_fields:
                null_count = int(row[col_name])
                pct = (null_count / total * 100) if total > 0 else 0
                status = "✅" if pct == 0 else "⚠️" if pct < 10 else "❌"
                print(f"  {status} {field_name:20s}: {null_count:6,} ({pct:5.2f}%)")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Check raw_skills table
    print("\n" + "="*80)
    print("📊 TABLE: raw_skills")
    print("-"*80)
    
    skills_query = f"""
    SELECT 
        COUNT(*) as total_rows,
        COUNTIF(skill_id IS NULL OR skill_id = '') as null_skill_id,
        COUNTIF(external_id IS NULL OR external_id = '') as null_external_id,
        COUNTIF(skill_name IS NULL OR skill_name = '') as null_skill_name,
        COUNTIF(skill_category IS NULL OR skill_category = '') as null_skill_category,
        COUNTIF(source IS NULL OR source = '') as null_source,
        COUNTIF(extracted_at IS NULL) as null_extracted_at
    FROM `{project_id}.{dataset}.raw_skills`
    """
    
    try:
        df = client.query(skills_query).to_dataframe()
        
        if not df.empty:
            row = df.iloc[0]
            total = int(row['total_rows'])
            
            print(f"Total Rows: {total:,}\n")
            
            fields = [
                ('skill_id', 'null_skill_id'),
                ('external_id', 'null_external_id'),
                ('skill_name', 'null_skill_name'),
                ('skill_category', 'null_skill_category'),
                ('source', 'null_source'),
                ('extracted_at', 'null_extracted_at'),
            ]
            
            for field_name, col_name in fields:
                null_count = int(row[col_name])
                pct = (null_count / total * 100) if total > 0 else 0
                status = "✅" if pct == 0 else "⚠️" if pct < 10 else "❌"
                print(f"  {status} {field_name:20s}: {null_count:6,} null ({pct:5.2f}%)")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Check raw_resumes table
    print("\n" + "="*80)
    print("📊 TABLE: raw_resumes")
    print("-"*80)
    
    resumes_query = f"""
    SELECT 
        COUNT(*) as total_rows,
        COUNTIF(resume_id IS NULL OR resume_id = '') as null_resume_id,
        COUNTIF(user_id IS NULL OR user_id = '') as null_user_id,
        COUNTIF(raw_text IS NULL OR raw_text = '') as null_raw_text,
        COUNTIF(file_name IS NULL OR file_name = '') as null_file_name,
        COUNTIF(file_size IS NULL OR file_size = 0) as null_file_size,
        COUNTIF(uploaded_at IS NULL) as null_uploaded_at,
        COUNTIF(processing_status IS NULL OR processing_status = '') as null_processing_status
    FROM `{project_id}.{dataset}.raw_resumes`
    """
    
    try:
        df = client.query(resumes_query).to_dataframe()
        
        if not df.empty:
            row = df.iloc[0]
            total = int(row['total_rows'])
            
            print(f"Total Rows: {total:,}\n")
            
            if total == 0:
                print("⚠️ No resumes in table!")
            else:
                fields = [
                    ('resume_id', 'null_resume_id'),
                    ('user_id', 'null_user_id'),
                    ('raw_text', 'null_raw_text'),
                    ('file_name', 'null_file_name'),
                    ('file_size', 'null_file_size'),
                    ('uploaded_at', 'null_uploaded_at'),
                    ('processing_status', 'null_processing_status'),
                ]
                
                for field_name, col_name in fields:
                    null_count = int(row[col_name])
                    pct = (null_count / total * 100) if total > 0 else 0
                    status = "✅" if pct == 0 else "⚠️" if pct < 10 else "❌"
                    print(f"  {status} {field_name:20s}: {null_count:6,} null ({pct:5.2f}%)")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Summary
    print("\n" + "="*80)
    print("📋 SUMMARY")
    print("="*80)
    
    # Get overall stats
    summary_query = f"""
    SELECT 
        'raw_jobs' as table_name,
        COUNT(*) as total_rows,
        COUNTIF(requirements IS NULL OR requirements = '') as critical_nulls
    FROM `{project_id}.{dataset}.raw_jobs`
    
    UNION ALL
    
    SELECT 
        'raw_skills' as table_name,
        COUNT(*) as total_rows,
        COUNTIF(skill_name IS NULL OR skill_name = '') as critical_nulls
    FROM `{project_id}.{dataset}.raw_skills`
    
    UNION ALL
    
    SELECT 
        'raw_resumes' as table_name,
        COUNT(*) as total_rows,
        COUNTIF(raw_text IS NULL OR raw_text = '') as critical_nulls
    FROM `{project_id}.{dataset}.raw_resumes`
    """
    
    try:
        df = client.query(summary_query).to_dataframe()
        
        print("\nTable Statistics:")
        for _, row in df.iterrows():
            table = row['table_name']
            total = int(row['total_rows'])
            critical = int(row['critical_nulls'])
            pct = (critical / total * 100) if total > 0 else 0
            status = "✅" if critical == 0 else "⚠️" if pct < 10 else "❌"
            print(f"  {status} {table:15s}: {total:6,} rows, {critical:6,} critical nulls ({pct:5.2f}%)")
        
        print("\n💡 Critical Fields:")
        print("  - raw_jobs.requirements: Must have skills for training")
        print("  - raw_skills.skill_name: Must have skill name")
        print("  - raw_resumes.raw_text: Must have resume text")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    deep_null_check()
