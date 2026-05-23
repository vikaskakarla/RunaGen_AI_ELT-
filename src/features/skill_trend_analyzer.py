"""
Phase 5: Skill Trend Analysis
Analyze skill demand trends from BigQuery data with role-based insights and graph data
"""
import os
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SkillTrendAnalyzer:
    """Analyze skill trends from job market data with role-based insights"""
    
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
        self.dataset = 'runagen_gold'
    
    def get_trending_skills(self, days: int = 30, limit: int = 20, role: str = None) -> List[Dict]:
        """Get trending skills in the last N days, filtered by role from actual job postings"""
        logger.info(f"📊 Analyzing trending skills (last {days} days) for role: {role or 'All'}...")
        
        if role:
            # Query skills from jobs that match the role
            query = f"""
            WITH role_jobs AS (
                SELECT 
                    j.job_id,
                    j.title,
                    j.company,
                    j.requirements,
                    j.scraped_at
                FROM `{self.project_id}.runagen_bronze.raw_jobs` j
                WHERE LOWER(j.title) LIKE LOWER('%{role}%')
                    AND j.scraped_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            ),
            skill_counts_raw AS (
                SELECT 
                    LOWER(TRIM(skill_name)) as skill_key,
                    ANY_VALUE(TRIM(skill_name)) as skill_display_name,
                    COUNT(DISTINCT rj.job_id) as demand_count,
                    COUNT(DISTINCT rj.company) as company_count
                FROM role_jobs rj
                CROSS JOIN UNNEST(SPLIT(rj.requirements, ',')) as skill_name
                WHERE LENGTH(TRIM(skill_name)) > 0
                GROUP BY skill_key
            )
            SELECT 
                sc.skill_display_name as skill_name,
                COALESCE(s.skill_category, 'Other') as skill_category,
                sc.demand_count,
                sc.company_count,
                ROUND(sc.demand_count * 100.0 / NULLIF((SELECT COUNT(DISTINCT job_id) FROM role_jobs), 0), 2) as demand_percentage
            FROM skill_counts_raw sc
            LEFT JOIN (
                SELECT LOWER(TRIM(skill_name)) as skill_key, ANY_VALUE(skill_category) as skill_category 
                FROM `{self.project_id}.runagen_bronze.raw_skills` 
                GROUP BY 1
            ) s ON sc.skill_key = s.skill_key
            WHERE sc.demand_count >= 1
            ORDER BY sc.demand_count DESC, sc.company_count DESC
            LIMIT {limit}
            """
        else:
            # Query all skills without role filter
            query = f"""
            WITH skill_counts_raw AS (
                SELECT 
                    LOWER(TRIM(skill_name)) as skill_key,
                    ANY_VALUE(TRIM(skill_name)) as skill_display_name,
                    COUNT(DISTINCT j.job_id) as demand_count,
                    COUNT(DISTINCT j.company) as company_count
                FROM `{self.project_id}.runagen_bronze.raw_jobs` j
                CROSS JOIN UNNEST(SPLIT(j.requirements, ',')) as skill_name
                WHERE j.scraped_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
                    AND LENGTH(TRIM(skill_name)) > 0
                GROUP BY skill_key
            )
            SELECT 
                sc.skill_display_name as skill_name,
                COALESCE(s.skill_category, 'Other') as skill_category,
                sc.demand_count,
                sc.company_count,
                ROUND(sc.demand_count * 100.0 / NULLIF((SELECT COUNT(DISTINCT job_id) FROM `{self.project_id}.runagen_bronze.raw_jobs`), 0), 2) as demand_percentage
            FROM skill_counts_raw sc
            LEFT JOIN (
                SELECT LOWER(TRIM(skill_name)) as skill_key, ANY_VALUE(skill_category) as skill_category 
                FROM `{self.project_id}.runagen_bronze.raw_skills` 
                GROUP BY 1
            ) s ON sc.skill_key = s.skill_key
            WHERE sc.demand_count >= 2
            ORDER BY sc.demand_count DESC, sc.company_count DESC
            LIMIT {limit}
            """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            if results.empty:
                logger.warning(f"No trending skills found for role: {role}")
                return []
            
            trends = []
            for _, row in results.iterrows():
                trends.append({
                    'skill_name': str(row['skill_name']).strip(),
                    'skill_category': str(row['skill_category']),
                    'demand_count': int(row['demand_count']),
                    'company_count': int(row['company_count']),
                    'demand_percentage': float(row['demand_percentage']),
                    'trend_direction': 'rising'
                })
            
            logger.info(f"✅ Found {len(trends)} trending skills for {role or 'all roles'}")
            return trends
        
        except Exception as e:
            logger.error(f"❌ Error analyzing trending skills: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_skill_growth_rate(self, skill_name: str, days: int = 90) -> Dict:
        """Calculate growth rate for a specific skill"""
        logger.info(f"📈 Calculating growth rate for {skill_name}...")
        
        query = f"""
        WITH daily_counts AS (
            SELECT 
                DATE(j.scraped_at) as date,
                COUNT(*) as job_count
            FROM `{self.project_id}.runagen_bronze.raw_jobs` j
            WHERE j.scraped_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
                AND LOWER(j.requirements) LIKE LOWER('%{skill_name}%')
            GROUP BY DATE(j.scraped_at)
        )
        SELECT 
            MIN(job_count) as min_jobs,
            MAX(job_count) as max_jobs,
            AVG(job_count) as avg_jobs,
            STDDEV(job_count) as stddev_jobs,
            COUNT(*) as days_with_data
        FROM daily_counts
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            if results.empty:
                return {
                    'skill_name': skill_name,
                    'growth_rate': 0,
                    'status': 'no_data'
                }
            
            row = results.iloc[0]
            min_jobs = float(row['min_jobs']) if row['min_jobs'] else 0
            max_jobs = float(row['max_jobs']) if row['max_jobs'] else 0
            
            growth_rate = ((max_jobs - min_jobs) / min_jobs * 100) if min_jobs > 0 else 0
            
            return {
                'skill_name': skill_name,
                'growth_rate': round(growth_rate, 2),
                'min_jobs': int(min_jobs),
                'max_jobs': int(max_jobs),
                'avg_jobs': round(float(row['avg_jobs']), 2),
                'days_analyzed': int(row['days_with_data']),
                'status': 'rising' if growth_rate > 10 else 'stable' if growth_rate > -10 else 'declining'
            }
        
        except Exception as e:
            logger.error(f"❌ Error calculating growth rate: {e}")
            return {'skill_name': skill_name, 'error': str(e)}
    
    def get_skill_salary_correlation(self, skill_name: str) -> Dict:
        """Get salary correlation for a specific skill"""
        logger.info(f"💰 Analyzing salary correlation for {skill_name}...")
        
        query = f"""
        SELECT 
            ROUND(AVG(salary_min), 2) as avg_min_salary,
            ROUND(AVG(salary_max), 2) as avg_max_salary,
            ROUND(AVG((salary_min + salary_max) / 2), 2) as avg_salary,
            COUNT(*) as job_count,
            MIN(salary_min) as min_salary,
            MAX(salary_max) as max_salary
        FROM `{self.project_id}.runagen_bronze.raw_jobs`
        WHERE LOWER(requirements) LIKE LOWER('%{skill_name}%')
            AND salary_min > 0
            AND salary_max > 0
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            if results.empty or results.iloc[0]['job_count'] == 0:
                return {
                    'skill_name': skill_name,
                    'status': 'no_salary_data'
                }
            
            row = results.iloc[0]
            
            return {
                'skill_name': skill_name,
                'avg_min_salary': float(row['avg_min_salary']),
                'avg_max_salary': float(row['avg_max_salary']),
                'avg_salary': float(row['avg_salary']),
                'min_salary': float(row['min_salary']),
                'max_salary': float(row['max_salary']),
                'job_count': int(row['job_count']),
                'salary_range': f"₹{row['avg_min_salary']:.0f}L - ₹{row['avg_max_salary']:.0f}L"
            }
        
        except Exception as e:
            logger.error(f"❌ Error analyzing salary correlation: {e}")
            return {'skill_name': skill_name, 'error': str(e)}
    
    def get_skill_by_category(self, category: str = None) -> List[Dict]:
        """Get skills grouped by category"""
        logger.info(f"🏷️  Analyzing skills by category...")
        
        category_filter = f"AND skill_category = '{category}'" if category else ""
        
        query = f"""
        SELECT 
            skill_category,
            skill_name,
            COUNT(*) as frequency
        FROM `{self.project_id}.runagen_bronze.raw_skills`
        WHERE skill_name IS NOT NULL
            {category_filter}
        GROUP BY skill_category, skill_name
        ORDER BY skill_category, frequency DESC
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            skills_by_category = []
            for _, row in results.iterrows():
                # Handle NaN values
                skill_category = row['skill_category']
                if pd.isna(skill_category):
                    skill_category = 'Other'
                
                skills_by_category.append({
                    'category': str(skill_category),
                    'skill_name': str(row['skill_name']).strip(),
                    'frequency': int(row['frequency'])
                })
            
            logger.info(f"✅ Found {len(skills_by_category)} skills")
            return skills_by_category
        
        except Exception as e:
            logger.error(f"❌ Error analyzing skills by category: {e}")
            return []
    
    def get_emerging_skills(self, threshold_days: int = 30, role: str = None) -> List[Dict]:
        """Identify emerging skills for a specific role based on recent job postings"""
        logger.info(f"🚀 Identifying emerging skills for role: {role or 'All'}...")
        
        if role:
            # Get skills from recent job postings for this role
            query = f"""
            WITH recent_skills AS (
                SELECT 
                    TRIM(skill_name) as skill_name,
                    j.scraped_at,
                    j.job_id
                FROM `{self.project_id}.runagen_bronze.raw_jobs` j
                CROSS JOIN UNNEST(SPLIT(j.requirements, ',')) as skill_name
                WHERE LOWER(j.title) LIKE LOWER('%{role}%')
                    AND j.scraped_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {threshold_days} DAY)
                    AND LENGTH(TRIM(skill_name)) > 0
            ),
            older_skills AS (
                SELECT 
                    TRIM(skill_name) as skill_name,
                    COUNT(DISTINCT j.job_id) as old_count
                FROM `{self.project_id}.runagen_bronze.raw_jobs` j
                CROSS JOIN UNNEST(SPLIT(j.requirements, ',')) as skill_name
                WHERE LOWER(j.title) LIKE LOWER('%{role}%')
                    AND j.scraped_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {threshold_days} DAY)
                    AND j.scraped_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {threshold_days * 2} DAY)
                    AND LENGTH(TRIM(skill_name)) > 0
                GROUP BY TRIM(skill_name)
            ),
            skill_analysis AS (
                SELECT 
                    rs.skill_name,
                    COUNT(DISTINCT rs.job_id) as recent_count,
                    COALESCE(os.old_count, 0) as old_count,
                    MIN(rs.scraped_at) as first_seen,
                    MAX(rs.scraped_at) as last_seen
                FROM recent_skills rs
                LEFT JOIN older_skills os ON rs.skill_name = os.skill_name
                GROUP BY rs.skill_name, os.old_count
            )
            SELECT 
                sa.skill_name,
                COALESCE(s.skill_category, 'Other') as skill_category,
                sa.recent_count,
                sa.old_count,
                sa.first_seen,
                sa.last_seen,
                ROUND((sa.recent_count - sa.old_count) * 100.0 / NULLIF(sa.old_count, 0), 2) as growth_rate
            FROM skill_analysis sa
            LEFT JOIN `{self.project_id}.runagen_bronze.raw_skills` s 
                ON LOWER(TRIM(sa.skill_name)) = LOWER(TRIM(s.skill_name))
            WHERE sa.recent_count >= 2
                AND (sa.old_count = 0 OR sa.recent_count > sa.old_count)
            ORDER BY 
                CASE WHEN sa.old_count = 0 THEN 1 ELSE 0 END DESC,
                growth_rate DESC,
                sa.recent_count DESC
            LIMIT 20
            """
        else:
            # Query without role filter
            query = f"""
            WITH recent_skills AS (
                SELECT 
                    LOWER(TRIM(skill_name)) as skill_key,
                    ANY_VALUE(TRIM(skill_name)) as skill_display_name,
                    j.scraped_at,
                    j.job_id
                FROM `{self.project_id}.runagen_bronze.raw_jobs` j
                CROSS JOIN UNNEST(SPLIT(j.requirements, ',')) as skill_name
                WHERE j.scraped_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {threshold_days} DAY)
                    AND LENGTH(TRIM(skill_name)) > 0
                GROUP BY skill_key, j.scraped_at, j.job_id
            ),
            skill_analysis AS (
                SELECT 
                    skill_key,
                    ANY_VALUE(skill_display_name) as skill_display_name,
                    COUNT(DISTINCT job_id) as recent_count,
                    MIN(scraped_at) as first_seen,
                    MAX(scraped_at) as last_seen
                FROM recent_skills
                GROUP BY skill_key
            )
            SELECT 
                sa.skill_display_name as skill_name,
                COALESCE(s.skill_category, 'Other') as skill_category,
                sa.recent_count,
                sa.first_seen,
                sa.last_seen
            FROM skill_analysis sa
            LEFT JOIN (
                SELECT LOWER(TRIM(skill_name)) as skill_key, ANY_VALUE(skill_category) as skill_category 
                FROM `{self.project_id}.runagen_bronze.raw_skills` 
                GROUP BY 1
            ) s ON sa.skill_key = s.skill_key
            WHERE sa.recent_count >= 2
            ORDER BY sa.recent_count DESC
            LIMIT 20
            """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            if results.empty:
                logger.warning(f"No emerging skills found for role: {role}")
                return []
            
            emerging = []
            for _, row in results.iterrows():
                skill_data = {
                    'skill_name': str(row['skill_name']).strip(),
                    'skill_category': str(row['skill_category']),
                    'recent_count': int(row['recent_count']),
                    'first_seen': str(row['first_seen']),
                    'last_seen': str(row['last_seen']),
                    'emergence_score': round(int(row['recent_count']) / threshold_days, 2)
                }
                
                # Add growth rate if available (role-based query)
                if 'growth_rate' in row and not pd.isna(row['growth_rate']):
                    skill_data['growth_rate'] = float(row['growth_rate'])
                    skill_data['old_count'] = int(row['old_count'])
                    skill_data['is_new'] = int(row['old_count']) == 0
                
                emerging.append(skill_data)
            
            logger.info(f"✅ Found {len(emerging)} emerging skills for {role or 'all roles'}")
            return emerging
        
        except Exception as e:
            logger.error(f"❌ Error identifying emerging skills: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_skill_demand_by_role(self, role: str) -> Dict:
        """Get skill demand for a specific role"""
        logger.info(f"👔 Analyzing skill demand for {role}...")
        
        query = f"""
        SELECT 
            LOWER(TRIM(skill_name)) as skill,
            COUNT(*) as demand_count
        FROM `{self.project_id}.runagen_bronze.raw_jobs` j
        CROSS JOIN UNNEST(SPLIT(j.requirements, ',')) as skill_name
        WHERE LOWER(j.title) LIKE LOWER('%{role}%')
        GROUP BY skill
        ORDER BY demand_count DESC
        LIMIT 15
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            skills = []
            for _, row in results.iterrows():
                skills.append({
                    'skill': row['skill'],
                    'demand_count': int(row['demand_count'])
                })
            
            return {
                'role': role,
                'top_skills': skills,
                'total_jobs': sum(s['demand_count'] for s in skills)
            }
        
        except Exception as e:
            logger.error(f"❌ Error analyzing skill demand by role: {e}")
            return {'role': role, 'error': str(e)}
    
    def generate_trend_report(self) -> Dict:
        """Generate comprehensive trend report"""
        logger.info("📋 Generating comprehensive trend report...")
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'trending_skills': self.get_trending_skills(days=30, limit=10),
            'emerging_skills': self.get_emerging_skills(threshold_days=30),
            'skill_categories': self.get_skill_by_category(),
            'role_skill_demand': {
                'data_analyst': self.get_skill_demand_by_role('Data Analyst'),
                'data_engineer': self.get_skill_demand_by_role('Data Engineer'),
                'backend_developer': self.get_skill_demand_by_role('Backend Developer'),
                'frontend_developer': self.get_skill_demand_by_role('Frontend Developer'),
            }
        }
        
        logger.info("✅ Trend report generated")
        return report
    
    def get_role_based_trends(self, role: str, days: int = 30) -> Dict:
        """Get comprehensive skill trends for a specific role with graph data"""
        logger.info(f"📊 Analyzing trends for {role}...")
        
        try:
            # Get top skills for this role
            skill_demand = self.get_skill_demand_by_role(role)
            
            # Get jobs for this role
            jobs = self._get_jobs_for_role(role, limit=20)
            
            # Get skill growth over time (for graph)
            top_skills = [s['skill'] for s in skill_demand.get('top_skills', [])[:5]]
            skill_timeline = self._get_skill_timeline(role, top_skills, days)
            
            # Get salary trends for this role
            salary_trends = self._get_role_salary_trends(role, days)
            
            # Prepare graph data
            graph_data = {
                'skill_demand_chart': {
                    'type': 'bar',
                    'labels': [s['skill'] for s in skill_demand.get('top_skills', [])[:10]],
                    'data': [s['demand_count'] for s in skill_demand.get('top_skills', [])[:10]],
                    'title': f'Top Skills for {role}',
                    'xlabel': 'Skills',
                    'ylabel': 'Job Postings'
                },
                'skill_timeline_chart': skill_timeline,
                'salary_trend_chart': salary_trends
            }
            
            return {
                'role': role,
                'analysis_period_days': days,
                'skill_demand': skill_demand,
                'available_jobs': jobs,
                'graph_data': graph_data,
                'summary': {
                    'total_jobs': len(jobs),
                    'top_skills_count': len(skill_demand.get('top_skills', [])),
                    'avg_salary': salary_trends.get('avg_salary', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing role-based trends: {e}")
            return {'role': role, 'error': str(e)}
    
    def _get_jobs_for_role(self, role: str, limit: int = 20) -> List[Dict]:
        """Get recent job postings for a specific role"""
        logger.info(f"🔍 Fetching jobs for {role}...")
        
        query = f"""
        SELECT 
            title,
            company,
            location,
            salary_min,
            salary_max,
            requirements,
            scraped_at
        FROM `{self.project_id}.runagen_bronze.raw_jobs`
        WHERE LOWER(title) LIKE LOWER('%{role}%')
        ORDER BY scraped_at DESC
        LIMIT {limit}
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            jobs = []
            for _, row in results.iterrows():
                jobs.append({
                    'title': str(row['title']),
                    'company': str(row['company']) if not pd.isna(row['company']) else 'N/A',
                    'location': str(row['location']) if not pd.isna(row['location']) else 'N/A',
                    'salary_min': int(row['salary_min']) if not pd.isna(row['salary_min']) and row['salary_min'] > 0 else None,
                    'salary_max': int(row['salary_max']) if not pd.isna(row['salary_max']) and row['salary_max'] > 0 else None,
                    'requirements': str(row['requirements'])[:200] if not pd.isna(row['requirements']) else '',
                    'posted_date': str(row['scraped_at'])
                })
            
            logger.info(f"✅ Found {len(jobs)} jobs for {role}")
            return jobs
            
        except Exception as e:
            logger.error(f"❌ Error fetching jobs: {e}")
            return []
    
    def _get_skill_timeline(self, role: str, skills: List[str], days: int = 30) -> Dict:
        """Get skill demand over time for graph visualization"""
        logger.info(f"📈 Generating skill timeline for {role}...")
        
        if not skills:
            return {}
        
        # Create timeline for last N days
        timeline_data = {
            'type': 'line',
            'title': f'Skill Demand Timeline for {role}',
            'xlabel': 'Date',
            'ylabel': 'Job Postings',
            'datasets': []
        }
        
        try:
            for skill in skills[:5]:  # Max 5 skills for readability
                query = f"""
                SELECT 
                    DATE(scraped_at) as date,
                    COUNT(*) as job_count
                FROM `{self.project_id}.runagen_bronze.raw_jobs`
                WHERE LOWER(title) LIKE LOWER('%{role}%')
                    AND LOWER(requirements) LIKE LOWER('%{skill}%')
                    AND scraped_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
                GROUP BY DATE(scraped_at)
                ORDER BY date
                """
                
                results = self.bq_client.query(query).to_dataframe()
                
                if not results.empty:
                    timeline_data['datasets'].append({
                        'label': skill,
                        'data': [int(row['job_count']) for _, row in results.iterrows()],
                        'dates': [str(row['date']) for _, row in results.iterrows()]
                    })
            
            return timeline_data
            
        except Exception as e:
            logger.error(f"❌ Error generating skill timeline: {e}")
            return {}
    
    def _get_role_salary_trends(self, role: str, days: int = 30) -> Dict:
        """Get salary trends for a role"""
        logger.info(f"💰 Analyzing salary trends for {role}...")
        
        query = f"""
        SELECT 
            DATE(scraped_at) as date,
            AVG(salary_min) as avg_min_salary,
            AVG(salary_max) as avg_max_salary,
            AVG((salary_min + salary_max) / 2) as avg_salary,
            COUNT(*) as job_count
        FROM `{self.project_id}.runagen_bronze.raw_jobs`
        WHERE LOWER(title) LIKE LOWER('%{role}%')
            AND salary_min > 0
            AND salary_max > 0
            AND scraped_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        GROUP BY DATE(scraped_at)
        ORDER BY date
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            if results.empty:
                return {'avg_salary': 0, 'chart': {}}
            
            # Calculate overall average
            overall_avg = results['avg_salary'].mean()
            
            # Prepare chart data
            chart_data = {
                'type': 'line',
                'title': f'Salary Trends for {role}',
                'xlabel': 'Date',
                'ylabel': 'Salary (INR)',
                'datasets': [
                    {
                        'label': 'Average Salary',
                        'data': [float(row['avg_salary']) for _, row in results.iterrows()],
                        'dates': [str(row['date']) for _, row in results.iterrows()]
                    },
                    {
                        'label': 'Min Salary',
                        'data': [float(row['avg_min_salary']) for _, row in results.iterrows()],
                        'dates': [str(row['date']) for _, row in results.iterrows()]
                    },
                    {
                        'label': 'Max Salary',
                        'data': [float(row['avg_max_salary']) for _, row in results.iterrows()],
                        'dates': [str(row['date']) for _, row in results.iterrows()]
                    }
                ]
            }
            
            return {
                'avg_salary': float(overall_avg),
                'min_salary': float(results['avg_min_salary'].min()),
                'max_salary': float(results['avg_max_salary'].max()),
                'chart': chart_data
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing salary trends: {e}")
            return {'avg_salary': 0, 'chart': {}}


def main():
    """Main execution"""
    print("\n" + "="*70)
    print("🚀 Phase 5: Skill Trend Analysis")
    print("="*70 + "\n")
    
    analyzer = SkillTrendAnalyzer()
    
    # Get trending skills
    print("📊 Top Trending Skills:")
    print("-"*70)
    trending = analyzer.get_trending_skills(days=30, limit=10)
    for i, skill in enumerate(trending, 1):
        print(f"{i}. {skill['skill_name']} ({skill['skill_category']})")
        print(f"   Demand: {skill['demand_count']} jobs ({skill['demand_percentage']}%)")
    
    # Get emerging skills
    print("\n🚀 Emerging Skills:")
    print("-"*70)
    emerging = analyzer.get_emerging_skills(threshold_days=30)
    for i, skill in enumerate(emerging[:5], 1):
        print(f"{i}. {skill['skill_name']} ({skill['skill_category']})")
        print(f"   Emergence Score: {skill['emergence_score']}")
    
    # Get skill demand by role
    print("\n👔 Skill Demand by Role:")
    print("-"*70)
    for role in ['Data Analyst', 'Data Engineer', 'Backend Developer']:
        demand = analyzer.get_skill_demand_by_role(role)
        print(f"\n{role}:")
        if 'top_skills' in demand:
            for skill in demand['top_skills'][:5]:
                print(f"  - {skill['skill']}: {skill['demand_count']} jobs")
    
    # Generate full report
    print("\n📋 Generating Full Report...")
    print("-"*70)
    report = analyzer.generate_trend_report()
    print(f"✅ Report generated with {len(report['trending_skills'])} trending skills")
    print(f"✅ Found {len(report['emerging_skills'])} emerging skills")
    
    print("\n" + "="*70)
    print("✅ Phase 5 Complete!")
    print("="*70 + "\n")
    
    return report


if __name__ == "__main__":
    main()
