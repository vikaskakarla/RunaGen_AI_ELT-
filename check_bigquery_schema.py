"""
Check actual BigQuery schema and sample data
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

def check_schema():
    """Check BigQuery schema and sample data"""
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
    
    print("="*70)
    print("🔍 BIGQUERY SCHEMA CHECK")
    print("="*70)
    
    # Check each table
    for table_name in ['raw_jobs', 'raw_skills', 'raw_resumes']:
        print(f"\n📊 Table: {table_name}")
        print("-"*70)
        
        try:
            table_id = f"{project_id}.{dataset}.{table_name}"
            table = client.get_table(table_id)
            
            print(f"   Total Rows: {table.num_rows:,}")
            print(f"\n   Schema:")
            for field in table.schema:
                print(f"      - {field.name}: {field.field_type} ({field.mode})")
            
            # Get sample data
            query = f"""
            SELECT *
            FROM `{table_id}`
            LIMIT 3
            """
            
            df = client.query(query).to_dataframe()
            
            if not df.empty:
                print(f"\n   Sample Data (first row):")
                for col in df.columns:
                    value = df[col].iloc[0]
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    print(f"      {col}: {value}")
                
                # Check for empty values
                print(f"\n   Empty Values:")
                for col in df.columns:
                    empty_count = df[col].isna().sum() + (df[col] == '').sum()
                    if empty_count > 0:
                        print(f"      {col}: {empty_count}/{len(df)} empty")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    check_schema()
