"""
BigQuery Data Quality Checker and Cleaner
Analyzes data quality, fills missing values, and improves preprocessing
"""
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd
import numpy as np
from datetime import datetime
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BigQueryDataCleaner:
    """Clean and preprocess BigQuery data to improve model accuracy"""
    
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
    
    def check_data_quality(self):
        """Comprehensive data quality check"""
        logger.info("="*70)
        logger.info("🔍 BIGQUERY DATA QUALITY ANALYSIS")
        logger.info("="*70)
        
        quality_report = {
            'jobs': self._check_jobs_quality(),
            'skills': self._check_skills_quality()
        }
        
        return quality_report
    
    def _check_jobs_quality(self):
        """Check raw_jobs table quality - CORRECT SCHEMA"""
        logger.info("\n📊 Analyzing raw_jobs table...")
        
        # Schema from ETL: job_id, external_id, source, title, company, location, 
        # description, requirements, salary_min, salary_max, currency, category, 
        # posted_date, scraped_at, url
        
        query = f"""
        WITH stats AS (
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT job_id) as unique_jobs,
                
                -- Missing values (matching actual schema)
                COUNTIF(title IS NULL OR title = '') as missing_title,
                COUNTIF(company IS NULL OR company = '') as missing_company,
                COUNTIF(location IS NULL OR location = '') as missing_location,
                COUNTIF(description IS NULL OR description = '') as missing_description,
                COUNTIF(requirements IS NULL OR requirements = '') as missing_requirements,
                COUNTIF(category IS NULL OR category = '') as missing_category,
                
                -- Salary analysis
                COUNTIF(salary_min IS NULL OR salary_min = 0) as missing_salary_min,
                COUNTIF(salary_max IS NULL OR salary_max = 0) as missing_salary_max,
                COUNTIF(salary_min > 0 AND salary_max > 0) as valid_salary_count,
                
                -- Salary statistics (for imputation)
                AVG(CASE WHEN salary_min > 0 THEN salary_min END) as avg_salary_min,
                AVG(CASE WHEN salary_max > 0 THEN salary_max END) as avg_salary_max
                
            FROM `{self.project_id}.{self.dataset}.raw_jobs`
        ),
        medians AS (
            SELECT 
                APPROX_QUANTILES(salary_min, 100)[OFFSET(50)] as median_salary_min,
                APPROX_QUANTILES(salary_max, 100)[OFFSET(50)] as median_salary_max
            FROM `{self.project_id}.{self.dataset}.raw_jobs`
            WHERE salary_min > 0 AND salary_max > 0
        )
        SELECT 
            stats.*,
            medians.median_salary_min,
            medians.median_salary_max
        FROM stats, medians
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            if results.empty:
                logger.warning("⚠️ raw_jobs table is empty!")
                return {}
            
            row = results.iloc[0]
            total = int(row['total_rows'])
            
            report = {
                'total_rows': total,
                'unique_jobs': int(row['unique_jobs']),
                'missing_percentages': {
                    'title': round(row['missing_title'] / total * 100, 2),
                    'company': round(row['missing_company'] / total * 100, 2),
                    'location': round(row['missing_location'] / total * 100, 2),
                    'description': round(row['missing_description'] / total * 100, 2),
                    'requirements': round(row['missing_requirements'] / total * 100, 2),
                    'salary_min': round(row['missing_salary_min'] / total * 100, 2),
                    'salary_max': round(row['missing_salary_max'] / total * 100, 2),
                },
                'salary_stats': {
                    'valid_count': int(row['valid_salary_count']),
                    'avg_min': float(row['avg_salary_min']) if pd.notna(row['avg_salary_min']) else 0,
                    'median_min': float(row['median_salary_min']) if pd.notna(row['median_salary_min']) else 0,
                    'avg_max': float(row['avg_salary_max']) if pd.notna(row['avg_salary_max']) else 0,
                    'median_max': float(row['median_salary_max']) if pd.notna(row['median_salary_max']) else 0,
                }
            }
            
            # Print report
            logger.info(f"   Total Jobs: {report['total_rows']:,}")
            logger.info(f"   Unique Jobs: {report['unique_jobs']:,}")
            logger.info(f"   Duplicates: {total - report['unique_jobs']:,}")
            logger.info("\n   Missing Data (%):")
            for field, pct in report['missing_percentages'].items():
                status = "❌" if pct > 50 else "⚠️" if pct > 20 else "✅"
                logger.info(f"      {status} {field}: {pct}%")
            
            logger.info(f"\n   Salary Statistics:")
            logger.info(f"      Valid Salaries: {report['salary_stats']['valid_count']:,} ({report['salary_stats']['valid_count']/total*100:.1f}%)")
            logger.info(f"      Avg Min: ₹{report['salary_stats']['avg_min']:,.0f}")
            logger.info(f"      Median Min: ₹{report['salary_stats']['median_min']:,.0f}")
            logger.info(f"      Avg Max: ₹{report['salary_stats']['avg_max']:,.0f}")
            logger.info(f"      Median Max: ₹{report['salary_stats']['median_max']:,.0f}")
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Error checking jobs quality: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _check_skills_quality(self):
        """Check raw_skills table quality"""
        logger.info("\n📊 Analyzing raw_skills table...")
        
        query = f"""
        SELECT 
            COUNT(*) as total_rows,
            COUNT(DISTINCT skill_name) as unique_skills,
            COUNTIF(skill_name IS NULL OR skill_name = '') as missing_skill_name,
            COUNTIF(skill_category IS NULL OR skill_category = '') as missing_category,
            COUNT(DISTINCT skill_category) as unique_categories
        FROM `{self.project_id}.{self.dataset}.raw_skills`
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            if results.empty:
                logger.warning("⚠️ raw_skills table is empty!")
                return {}
            
            row = results.iloc[0]
            total = int(row['total_rows'])
            
            report = {
                'total_rows': total,
                'unique_skills': int(row['unique_skills']),
                'unique_categories': int(row['unique_categories']),
                'missing_percentages': {
                    'skill_name': round(row['missing_skill_name'] / total * 100, 2),
                    'skill_category': round(row['missing_category'] / total * 100, 2),
                }
            }
            
            logger.info(f"   Total Skill Records: {report['total_rows']}")
            logger.info(f"   Unique Skills: {report['unique_skills']}")
            logger.info(f"   Unique Categories: {report['unique_categories']}")
            logger.info(f"   Missing skill_name: {report['missing_percentages']['skill_name']}%")
            logger.info(f"   Missing category: {report['missing_percentages']['skill_category']}%")
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Error checking skills quality: {e}")
            return {}
    
    def _check_resumes_quality(self):
        """Check raw_resumes table quality - CORRECT SCHEMA"""
        logger.info("\n📊 Analyzing raw_resumes table...")
        
        # Schema from ETL: resume_id, user_id, raw_text, file_name, 
        # file_size, uploaded_at, processing_status
        
        query = f"""
        SELECT 
            COUNT(*) as total_rows,
            COUNTIF(raw_text IS NULL OR raw_text = '') as missing_text,
            COUNTIF(user_id IS NULL OR user_id = '') as missing_user_id,
            COUNTIF(file_name IS NULL OR file_name = '') as missing_file_name,
            COUNTIF(processing_status IS NULL OR processing_status = '') as missing_status
        FROM `{self.project_id}.{self.dataset}.raw_resumes`
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            if results.empty:
                logger.warning("⚠️ raw_resumes table is empty!")
                return {}
            
            row = results.iloc[0]
            total = int(row['total_rows'])
            
            if total == 0:
                logger.warning("⚠️ No resumes in table!")
                return {'total_rows': 0}
            
            report = {
                'total_rows': total,
                'missing_percentages': {
                    'raw_text': round(row['missing_text'] / total * 100, 2),
                    'user_id': round(row['missing_user_id'] / total * 100, 2),
                    'file_name': round(row['missing_file_name'] / total * 100, 2),
                    'processing_status': round(row['missing_status'] / total * 100, 2),
                }
            }
            
            logger.info(f"   Total Resumes: {report['total_rows']}")
            for field, pct in report['missing_percentages'].items():
                status = "❌" if pct > 50 else "⚠️" if pct > 20 else "✅"
                logger.info(f"      {status} {field}: {pct}%")
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Error checking resumes quality: {e}")
            return {}
    
    def remove_empty_requirements(self, dry_run=True):
        """Remove jobs with empty requirements/skills (can't be imputed)"""
        logger.info("\n🔧 REMOVING JOBS WITH EMPTY REQUIREMENTS")
        logger.info("="*70)
        
        # Count jobs with empty requirements (matching actual schema)
        count_query = f"""
        SELECT COUNT(*) as empty_count
        FROM `{self.project_id}.{self.dataset}.raw_jobs`
        WHERE requirements IS NULL OR requirements = '' OR TRIM(requirements) = ''
        """
        
        try:
            empty_count = self.bq_client.query(count_query).to_dataframe().iloc[0]['empty_count']
            logger.info(f"   Jobs with empty requirements: {empty_count:,}")
            
            if empty_count == 0:
                logger.info("   ✅ No jobs with empty requirements!")
                return 0
            
            if dry_run:
                logger.info("\n   ℹ️ DRY RUN MODE - No changes will be made")
                logger.info("   These jobs would be removed (useless for training)")
                return empty_count
            
            # Delete jobs with empty requirements
            delete_query = f"""
            DELETE FROM `{self.project_id}.{self.dataset}.raw_jobs`
            WHERE requirements IS NULL OR requirements = '' OR TRIM(requirements) = ''
            """
            
            logger.info("\n   🗑️ Removing jobs with empty requirements...")
            job = self.bq_client.query(delete_query)
            job.result()
            
            logger.info(f"   ✅ Removed {empty_count:,} jobs with empty requirements!")
            logger.info("   Reason: Jobs without skills are useless for model training")
            
            return empty_count
            
        except Exception as e:
            logger.error(f"❌ Error removing empty requirements: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def fill_missing_salaries(self, dry_run=True):
        """Fill missing salaries using role-based median/mean - CORRECT SCHEMA"""
        logger.info("\n🔧 FILLING MISSING SALARIES")
        logger.info("="*70)
        
        # Get salary statistics by role using APPROX_QUANTILES for median
        # Extract role from title field (matching actual schema)
        query = f"""
        WITH role_salaries AS (
            SELECT 
                title,
                salary_min,
                salary_max,
                -- Extract role category from title
                CASE 
                    WHEN LOWER(title) LIKE '%data scientist%' THEN 'Data Scientist'
                    WHEN LOWER(title) LIKE '%data engineer%' THEN 'Data Engineer'
                    WHEN LOWER(title) LIKE '%data analyst%' THEN 'Data Analyst'
                    WHEN LOWER(title) LIKE '%software engineer%' OR LOWER(title) LIKE '%software developer%' THEN 'Software Engineer'
                    WHEN LOWER(title) LIKE '%backend%' OR LOWER(title) LIKE '%back end%' OR LOWER(title) LIKE '%back-end%' THEN 'Backend Developer'
                    WHEN LOWER(title) LIKE '%frontend%' OR LOWER(title) LIKE '%front end%' OR LOWER(title) LIKE '%front-end%' THEN 'Frontend Developer'
                    WHEN LOWER(title) LIKE '%full stack%' OR LOWER(title) LIKE '%fullstack%' OR LOWER(title) LIKE '%full-stack%' THEN 'Full Stack Developer'
                    WHEN LOWER(title) LIKE '%devops%' OR LOWER(title) LIKE '%sre%' THEN 'DevOps Engineer'
                    WHEN LOWER(title) LIKE '%machine learning%' OR LOWER(title) LIKE '%ml engineer%' OR LOWER(title) LIKE '%ai engineer%' THEN 'ML Engineer'
                    WHEN LOWER(title) LIKE '%product manager%' OR LOWER(title) LIKE '%pm%' THEN 'Product Manager'
                    WHEN LOWER(title) LIKE '%qa%' OR LOWER(title) LIKE '%test%' OR LOWER(title) LIKE '%quality%' THEN 'QA Engineer'
                    ELSE 'Other'
                END as role_category
            FROM `{self.project_id}.{self.dataset}.raw_jobs`
            WHERE salary_min > 0 AND salary_max > 0
        )
        SELECT 
            role_category,
            COUNT(*) as count,
            CAST(ROUND(AVG(salary_min), 0) AS INT64) as avg_min,
            CAST(APPROX_QUANTILES(salary_min, 100)[OFFSET(50)] AS INT64) as median_min,
            CAST(ROUND(AVG(salary_max), 0) AS INT64) as avg_max,
            CAST(APPROX_QUANTILES(salary_max, 100)[OFFSET(50)] AS INT64) as median_max
        FROM role_salaries
        GROUP BY role_category
        ORDER BY count DESC
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            if results.empty:
                logger.warning("⚠️ No salary data available for imputation")
                return
            
            # Create imputation map
            salary_map = {}
            logger.info("\n📊 Role-Based Salary Statistics:")
            for _, row in results.iterrows():
                role = row['role_category']
                salary_map[role] = {
                    'median_min': int(row['median_min']),
                    'median_max': int(row['median_max']),
                    'avg_min': int(row['avg_min']),
                    'avg_max': int(row['avg_max']),
                    'count': int(row['count'])
                }
                logger.info(f"   {role}: {row['count']} jobs, Median: ₹{row['median_min']:,.0f} - ₹{row['median_max']:,.0f}")
            
            # Count jobs with missing salaries
            count_query = f"""
            SELECT COUNT(*) as missing_count
            FROM `{self.project_id}.{self.dataset}.raw_jobs`
            WHERE salary_min IS NULL OR salary_min = 0 OR salary_max IS NULL OR salary_max = 0
            """
            
            missing_count = self.bq_client.query(count_query).to_dataframe().iloc[0]['missing_count']
            logger.info(f"\n   Jobs with missing salaries: {missing_count}")
            
            if dry_run:
                logger.info("\n   ℹ️ DRY RUN MODE - No changes will be made")
                logger.info("   Run with dry_run=False to apply changes")
                return salary_map
            
            # Update missing salaries (use median as it's more robust to outliers)
            logger.info("\n   🔄 Updating missing salaries...")
            
            for role, stats in salary_map.items():
                # Match the same CASE statement used in the query
                update_query = f"""
                UPDATE `{self.project_id}.{self.dataset}.raw_jobs`
                SET 
                    salary_min = {stats['median_min']},
                    salary_max = {stats['median_max']}
                WHERE (salary_min IS NULL OR salary_min = 0 OR salary_max IS NULL OR salary_max = 0)
                    AND CASE 
                        WHEN LOWER(title) LIKE '%data scientist%' THEN 'Data Scientist'
                        WHEN LOWER(title) LIKE '%data engineer%' THEN 'Data Engineer'
                        WHEN LOWER(title) LIKE '%data analyst%' THEN 'Data Analyst'
                        WHEN LOWER(title) LIKE '%software engineer%' OR LOWER(title) LIKE '%software developer%' THEN 'Software Engineer'
                        WHEN LOWER(title) LIKE '%backend%' OR LOWER(title) LIKE '%back end%' OR LOWER(title) LIKE '%back-end%' THEN 'Backend Developer'
                        WHEN LOWER(title) LIKE '%frontend%' OR LOWER(title) LIKE '%front end%' OR LOWER(title) LIKE '%front-end%' THEN 'Frontend Developer'
                        WHEN LOWER(title) LIKE '%full stack%' OR LOWER(title) LIKE '%fullstack%' OR LOWER(title) LIKE '%full-stack%' THEN 'Full Stack Developer'
                        WHEN LOWER(title) LIKE '%devops%' OR LOWER(title) LIKE '%sre%' THEN 'DevOps Engineer'
                        WHEN LOWER(title) LIKE '%machine learning%' OR LOWER(title) LIKE '%ml engineer%' OR LOWER(title) LIKE '%ai engineer%' THEN 'ML Engineer'
                        WHEN LOWER(title) LIKE '%product manager%' OR LOWER(title) LIKE '%pm%' THEN 'Product Manager'
                        WHEN LOWER(title) LIKE '%qa%' OR LOWER(title) LIKE '%test%' OR LOWER(title) LIKE '%quality%' THEN 'QA Engineer'
                        ELSE 'Other'
                    END = '{role}'
                """
                
                job = self.bq_client.query(update_query)
                job.result()  # Wait for completion
                logger.info(f"      ✅ Updated {role} salaries")
            
            logger.info(f"\n   ✅ Successfully filled missing salaries!")
            return salary_map
            
        except Exception as e:
            logger.error(f"❌ Error filling missing salaries: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def remove_duplicates(self, dry_run=True):
        """Remove duplicate job postings"""
        logger.info("\n🔧 REMOVING DUPLICATE JOBS")
        logger.info("="*70)
        
        # Find duplicates
        query = f"""
        SELECT 
            COUNT(*) as total_duplicates
        FROM (
            SELECT job_id, COUNT(*) as cnt
            FROM `{self.project_id}.{self.dataset}.raw_jobs`
            GROUP BY job_id
            HAVING COUNT(*) > 1
        )
        """
        
        try:
            result = self.bq_client.query(query).to_dataframe()
            duplicates = int(result.iloc[0]['total_duplicates'])
            
            logger.info(f"   Found {duplicates} duplicate job IDs")
            
            if duplicates == 0:
                logger.info("   ✅ No duplicates found!")
                return
            
            if dry_run:
                logger.info("   ℹ️ DRY RUN MODE - No changes will be made")
                return
            
            # Keep only the most recent entry for each job_id
            dedup_query = f"""
            CREATE OR REPLACE TABLE `{self.project_id}.{self.dataset}.raw_jobs` AS
            SELECT * EXCEPT(row_num)
            FROM (
                SELECT *, ROW_NUMBER() OVER(PARTITION BY job_id ORDER BY scraped_at DESC) as row_num
                FROM `{self.project_id}.{self.dataset}.raw_jobs`
            )
            WHERE row_num = 1
            """
            
            job = self.bq_client.query(dedup_query)
            job.result()
            
            logger.info(f"   ✅ Removed {duplicates} duplicate jobs!")
            
        except Exception as e:
            logger.error(f"❌ Error removing duplicates: {e}")
    
    def standardize_categories(self, dry_run=True):
        """Standardize skill categories"""
        logger.info("\n🔧 STANDARDIZING SKILL CATEGORIES")
        logger.info("="*70)
        
        # Check current categories
        query = f"""
        SELECT skill_category, COUNT(*) as count
        FROM `{self.project_id}.{self.dataset}.raw_skills`
        WHERE skill_category IS NOT NULL AND skill_category != ''
        GROUP BY skill_category
        ORDER BY count DESC
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            logger.info(f"   Current categories: {len(results)}")
            for _, row in results.head(10).iterrows():
                logger.info(f"      - {row['skill_category']}: {row['count']}")
            
            if dry_run:
                logger.info("   ℹ️ DRY RUN MODE - No changes will be made")
                return
            
            # Standardize common variations
            update_query = f"""
            UPDATE `{self.project_id}.{self.dataset}.raw_skills`
            SET skill_category = CASE
                WHEN LOWER(skill_category) LIKE '%program%' THEN 'Programming'
                WHEN LOWER(skill_category) LIKE '%database%' OR LOWER(skill_category) LIKE '%sql%' THEN 'Database'
                WHEN LOWER(skill_category) LIKE '%cloud%' OR LOWER(skill_category) LIKE '%aws%' OR LOWER(skill_category) LIKE '%azure%' THEN 'Cloud'
                WHEN LOWER(skill_category) LIKE '%framework%' THEN 'Framework'
                WHEN LOWER(skill_category) LIKE '%tool%' THEN 'Tool'
                WHEN LOWER(skill_category) LIKE '%data%' THEN 'Data Science'
                WHEN LOWER(skill_category) LIKE '%machine%' OR LOWER(skill_category) LIKE '%ml%' OR LOWER(skill_category) LIKE '%ai%' THEN 'Machine Learning'
                WHEN LOWER(skill_category) LIKE '%web%' THEN 'Web Development'
                WHEN LOWER(skill_category) LIKE '%mobile%' THEN 'Mobile Development'
                WHEN skill_category IS NULL OR skill_category = '' THEN 'Other'
                ELSE skill_category
            END
            WHERE TRUE
            """
            
            job = self.bq_client.query(update_query)
            job.result()
            
            logger.info("   ✅ Standardized skill categories!")
            
        except Exception as e:
            logger.error(f"❌ Error standardizing categories: {e}")
    
    def generate_cleaning_report(self):
        """Generate comprehensive cleaning report"""
        logger.info("\n" + "="*70)
        logger.info("📋 DATA CLEANING RECOMMENDATIONS")
        logger.info("="*70)
        
        quality = self.check_data_quality()
        
        recommendations = []
        
        # Check jobs
        if quality.get('jobs'):
            jobs = quality['jobs']
            
            # Empty requirements - MUST REMOVE
            if jobs['missing_percentages']['requirements'] > 0:
                recommendations.append({
                    'priority': 'CRITICAL',
                    'issue': f"Empty requirements: {jobs['missing_percentages']['requirements']}%",
                    'action': 'Run remove_empty_requirements() to DELETE these rows',
                    'impact': 'Jobs without skills are useless for training - MUST REMOVE',
                    'reason': 'Cannot impute skills - they are job-specific'
                })
            
            # Missing salaries - CAN IMPUTE
            if jobs['missing_percentages']['salary_min'] > 30:
                recommendations.append({
                    'priority': 'HIGH',
                    'issue': f"Missing salaries: {jobs['missing_percentages']['salary_min']}%",
                    'action': 'Run fill_missing_salaries() to impute using role-based medians',
                    'impact': 'Improves salary prediction model accuracy',
                    'reason': 'Numerical values can be imputed with median'
                })
            
            # Duplicates
            if jobs['total_rows'] - jobs['unique_jobs'] > 0:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'issue': f"Duplicate jobs: {jobs['total_rows'] - jobs['unique_jobs']:,}",
                    'action': 'Run remove_duplicates() to clean data',
                    'impact': 'Reduces model overfitting'
                })
        
        # Check skills
        if quality.get('skills'):
            skills = quality['skills']
            if skills['missing_percentages']['skill_category'] > 20:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'issue': f"Missing skill categories: {skills['missing_percentages']['skill_category']}%",
                    'action': 'Run standardize_categories() to fill and standardize',
                    'impact': 'Better skill classification'
                })
        
        logger.info("\n🎯 Recommendations:")
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"\n   {i}. [{rec['priority']}] {rec['issue']}")
            logger.info(f"      Action: {rec['action']}")
            logger.info(f"      Impact: {rec['impact']}")
            logger.info(f"      Reason: {rec['reason']}")
        
        if not recommendations:
            logger.info("\n   ✅ Data quality looks good!")
        
        logger.info("\n" + "="*70)
        
        return recommendations


def main():
    """Main execution"""
    cleaner = BigQueryDataCleaner()
    
    # 1. Check data quality
    quality_report = cleaner.check_data_quality()
    
    # 2. Generate recommendations
    recommendations = cleaner.generate_cleaning_report()
    
    # 3. Ask user if they want to apply fixes
    if recommendations:
        print("\n" + "="*70)
        print("🔧 APPLY FIXES?")
        print("="*70)
        print("\nDo you want to apply the recommended fixes?")
        print("1. Yes - Apply all fixes")
        print("2. No - Just show report (dry run)")
        print("3. Custom - Choose which fixes to apply")
        
        choice = input("\nEnter choice (1/2/3): ").strip()
        
        if choice == "1":
            print("\n🚀 Applying all fixes...")
            
            # CRITICAL: Remove empty requirements first
            print("\n1️⃣ Removing jobs with empty requirements...")
            cleaner.remove_empty_requirements(dry_run=False)
            
            # HIGH: Fill missing salaries
            print("\n2️⃣ Filling missing salaries...")
            cleaner.fill_missing_salaries(dry_run=False)
            
            # MEDIUM: Remove duplicates
            print("\n3️⃣ Removing duplicates...")
            cleaner.remove_duplicates(dry_run=False)
            
            # MEDIUM: Standardize categories
            print("\n4️⃣ Standardizing skill categories...")
            cleaner.standardize_categories(dry_run=False)
            
            print("\n✅ All fixes applied!")
            
        elif choice == "3":
            print("\n📋 Custom fixes:")
            if input("Remove jobs with empty requirements? (y/n): ").lower() == 'y':
                cleaner.remove_empty_requirements(dry_run=False)
            if input("Fill missing salaries? (y/n): ").lower() == 'y':
                cleaner.fill_missing_salaries(dry_run=False)
            if input("Remove duplicates? (y/n): ").lower() == 'y':
                cleaner.remove_duplicates(dry_run=False)
            if input("Standardize categories? (y/n): ").lower() == 'y':
                cleaner.standardize_categories(dry_run=False)
        else:
            print("\n✅ Dry run complete - no changes made")


if __name__ == "__main__":
    main()
