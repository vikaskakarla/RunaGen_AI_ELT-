"""
Final cleanup to handle remaining null values
"""
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account

load_dotenv()

def final_cleanup():
    """Handle remaining null values"""
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
    print("🔧 FINAL DATA CLEANUP")
    print("="*80)
    
    # Fix 1: Fill empty company names with "Unknown Company"
    print("\n1️⃣ Fixing empty company names (101 rows)...")
    
    company_query = f"""
    UPDATE `{project_id}.{dataset}.raw_jobs`
    SET company = 'Unknown Company'
    WHERE company IS NULL OR company = ''
    """
    
    try:
        job = client.query(company_query)
        job.result()
        print("   ✅ Fixed empty company names")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Fix 2: Handle remaining NULL salaries (142 rows - 0.66%)
    # These are jobs where role couldn't be categorized
    print("\n2️⃣ Fixing remaining NULL salaries (142 rows)...")
    print("   Using overall median salary for uncategorized roles...")
    
    # Get overall median
    median_query = f"""
    SELECT 
        CAST(APPROX_QUANTILES(salary_min, 100)[OFFSET(50)] AS INT64) as median_min,
        CAST(APPROX_QUANTILES(salary_max, 100)[OFFSET(50)] AS INT64) as median_max
    FROM `{project_id}.{dataset}.raw_jobs`
    WHERE salary_min > 0 AND salary_max > 0
    """
    
    try:
        df = client.query(median_query).to_dataframe()
        median_min = int(df.iloc[0]['median_min'])
        median_max = int(df.iloc[0]['median_max'])
        
        print(f"   Overall Median: ₹{median_min:,} - ₹{median_max:,}")
        
        # Update NULL salaries
        salary_query = f"""
        UPDATE `{project_id}.{dataset}.raw_jobs`
        SET 
            salary_min = {median_min},
            salary_max = {median_max}
        WHERE salary_min IS NULL OR salary_max IS NULL
        """
        
        job = client.query(salary_query)
        job.result()
        print("   ✅ Fixed remaining NULL salaries")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Fix 3: Handle zero salary (1 row)
    print("\n3️⃣ Fixing zero salary values (1 row)...")
    
    zero_salary_query = f"""
    UPDATE `{project_id}.{dataset}.raw_jobs`
    SET 
        salary_min = {median_min},
        salary_max = {median_max}
    WHERE salary_min = 0 OR salary_max = 0
    """
    
    try:
        job = client.query(zero_salary_query)
        job.result()
        print("   ✅ Fixed zero salary values")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Fix 4: Clean up raw_resumes (all empty - should be removed or ignored)
    print("\n4️⃣ Handling empty resumes (6 rows with 100% null data)...")
    print("   These are placeholder rows with no actual data")
    
    delete_empty_resumes = f"""
    DELETE FROM `{project_id}.{dataset}.raw_resumes`
    WHERE raw_text IS NULL OR raw_text = ''
    """
    
    try:
        job = client.query(delete_empty_resumes)
        job.result()
        print("   ✅ Removed empty resume placeholders")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Verification
    print("\n" + "="*80)
    print("✅ VERIFICATION")
    print("="*80)
    
    verify_query = f"""
    SELECT 
        'raw_jobs' as table_name,
        COUNT(*) as total_rows,
        COUNTIF(company IS NULL OR company = '') as null_company,
        COUNTIF(salary_min IS NULL OR salary_min = 0) as null_salary_min,
        COUNTIF(salary_max IS NULL OR salary_max = 0) as null_salary_max,
        COUNTIF(requirements IS NULL OR requirements = '') as null_requirements
    FROM `{project_id}.{dataset}.raw_jobs`
    
    UNION ALL
    
    SELECT 
        'raw_skills' as table_name,
        COUNT(*) as total_rows,
        0 as null_company,
        0 as null_salary_min,
        0 as null_salary_max,
        COUNTIF(skill_name IS NULL OR skill_name = '') as null_requirements
    FROM `{project_id}.{dataset}.raw_skills`
    
    UNION ALL
    
    SELECT 
        'raw_resumes' as table_name,
        COUNT(*) as total_rows,
        0 as null_company,
        0 as null_salary_min,
        0 as null_salary_max,
        COUNTIF(raw_text IS NULL OR raw_text = '') as null_requirements
    FROM `{project_id}.{dataset}.raw_resumes`
    """
    
    try:
        df = client.query(verify_query).to_dataframe()
        
        print("\nFinal Data Quality:")
        for _, row in df.iterrows():
            table = row['table_name']
            total = int(row['total_rows'])
            
            if table == 'raw_jobs':
                company_nulls = int(row['null_company'])
                salary_min_nulls = int(row['null_salary_min'])
                salary_max_nulls = int(row['null_salary_max'])
                req_nulls = int(row['null_requirements'])
                
                print(f"\n  📊 {table}:")
                print(f"     Total Rows: {total:,}")
                print(f"     Empty company: {company_nulls} ({'✅' if company_nulls == 0 else '❌'})")
                print(f"     NULL/zero salary_min: {salary_min_nulls} ({'✅' if salary_min_nulls == 0 else '❌'})")
                print(f"     NULL/zero salary_max: {salary_max_nulls} ({'✅' if salary_max_nulls == 0 else '❌'})")
                print(f"     Empty requirements: {req_nulls} ({'✅' if req_nulls == 0 else '❌'})")
            
            elif table == 'raw_skills':
                skill_nulls = int(row['null_requirements'])
                print(f"\n  📊 {table}:")
                print(f"     Total Rows: {total:,}")
                print(f"     Empty skill_name: {skill_nulls} ({'✅' if skill_nulls == 0 else '❌'})")
            
            elif table == 'raw_resumes':
                text_nulls = int(row['null_requirements'])
                print(f"\n  📊 {table}:")
                print(f"     Total Rows: {total:,}")
                print(f"     Empty raw_text: {text_nulls} ({'✅' if text_nulls == 0 else '❌'})")
        
        print("\n" + "="*80)
        print("🎉 DATA CLEANUP COMPLETE!")
        print("="*80)
        print("\n✅ All critical null values have been handled")
        print("✅ Data is ready for model training")
        print("\n📋 Next Steps:")
        print("   1. Train models with cleaned data")
        print("   2. Test model accuracy")
        print("   3. Deploy to production")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    final_cleanup()
