"""
Phase 6: Resume Optimization Engine
Optimize resumes based on job requirements and skill trends
Enhanced with Ollama AI for intelligent suggestions
"""
import os
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd
from typing import Dict, List, Tuple
import json
import logging
import re
from collections import Counter
import requests

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResumeOptimizer:
    """Optimize resumes for better job matching with Ollama AI"""
    
    def __init__(self):
        """Initialize BigQuery client, skill database, and Ollama"""
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
        
        # Ollama configuration
        self.ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self.ollama_model = os.getenv('OLLAMA_MODEL', 'llama3.2:3b')
        self.use_ollama = self._check_ollama_available()
        
        # Load skill database
        self.skills_db = self._load_skills_database()
    
    def _check_ollama_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                logger.info(f"✓ Ollama available at {self.ollama_url}")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Ollama not available: {e}")
        return False
    
    def _call_ollama(self, prompt: str, max_tokens: int = 500) -> str:
        """Call Ollama API for text generation"""
        if not self.use_ollama:
            return ""
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7
                    }
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
        except Exception as e:
            logger.error(f"❌ Ollama API error: {e}")
        
        return ""
    
    def _load_skills_database(self) -> Dict[str, List[str]]:
        """Load skills database from BigQuery"""
        logger.info("📚 Loading skills database...")
        
        query = f"""
        SELECT skill_category, skill_name
        FROM `{self.project_id}.runagen_bronze.raw_skills`
        WHERE skill_name IS NOT NULL
        GROUP BY skill_category, skill_name
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            skills_by_category = {}
            for _, row in results.iterrows():
                category = row['skill_category'] or 'Other'
                if category not in skills_by_category:
                    skills_by_category[category] = []
                skills_by_category[category].append(row['skill_name'].lower())
            
            logger.info(f"✅ Loaded {sum(len(v) for v in skills_by_category.values())} skills")
            return skills_by_category
        
        except Exception as e:
            logger.error(f"❌ Error loading skills database: {e}")
            return {}
    
    def extract_skills_from_resume(self, resume_text: str) -> Dict[str, List[str]]:
        """Extract skills from resume text - Enhanced with comprehensive skill detection and AI"""
        logger.info("🔍 Extracting skills from resume...")
        
        resume_lower = resume_text.lower()
        found_skills = {}
        
        # 1. First, extract from BigQuery skills database
        for category, skills in self.skills_db.items():
            found_skills[category] = []
            for skill in skills:
                # Use word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(skill) + r'\b'
                if re.search(pattern, resume_lower):
                    found_skills[category].append(skill)
        
        # 2. Add comprehensive common technical skills
        common_skills = {
            'Programming Languages': [
                'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'php', 
                'swift', 'kotlin', 'go', 'rust', 'scala', 'r', 'matlab', 'perl', 'shell',
                'bash', 'powershell', 'sql', 'pl/sql', 't-sql', 'nosql'
            ],
            'Web Technologies': [
                'html', 'css', 'react', 'angular', 'vue', 'node.js', 'express', 'django',
                'flask', 'spring', 'asp.net', 'jquery', 'bootstrap', 'tailwind', 'sass',
                'webpack', 'next.js', 'nuxt.js', 'gatsby', 'redux', 'graphql', 'rest api',
                'restful', 'soap', 'ajax', 'json', 'xml'
            ],
            'Databases': [
                'mysql', 'postgresql', 'mongodb', 'redis', 'cassandra', 'oracle', 
                'sql server', 'sqlite', 'dynamodb', 'elasticsearch', 'neo4j', 'mariadb',
                'couchdb', 'firebase', 'bigquery', 'snowflake', 'redshift'
            ],
            'Cloud & DevOps': [
                'aws', 'azure', 'gcp', 'google cloud', 'docker', 'kubernetes', 'jenkins',
                'gitlab', 'github actions', 'terraform', 'ansible', 'chef', 'puppet',
                'ci/cd', 'devops', 'linux', 'unix', 'nginx', 'apache', 'microservices',
                'serverless', 'lambda', 'ec2', 's3', 'cloudformation'
            ],
            'Data Science & ML': [
                'machine learning', 'deep learning', 'neural networks', 'tensorflow',
                'pytorch', 'keras', 'scikit-learn', 'pandas', 'numpy', 'matplotlib',
                'seaborn', 'nlp', 'computer vision', 'data analysis', 'data visualization',
                'tableau', 'power bi', 'spark', 'hadoop', 'kafka', 'airflow', 'etl',
                'data engineering', 'data mining', 'statistics', 'predictive modeling'
            ],
            'Mobile Development': [
                'android', 'ios', 'react native', 'flutter', 'xamarin', 'swift', 'kotlin',
                'objective-c', 'mobile development', 'app development'
            ],
            'Tools & Methodologies': [
                'git', 'github', 'gitlab', 'bitbucket', 'jira', 'confluence', 'agile',
                'scrum', 'kanban', 'tdd', 'bdd', 'unit testing', 'integration testing',
                'selenium', 'jest', 'pytest', 'junit', 'postman', 'swagger', 'api testing',
                'performance testing', 'load testing', 'security testing'
            ],
            'Soft Skills': [
                'leadership', 'team management', 'project management', 'communication',
                'problem solving', 'analytical', 'collaboration', 'mentoring', 'coaching'
            ]
        }
        
        for category, skills in common_skills.items():
            if category not in found_skills:
                found_skills[category] = []
            
            for skill in skills:
                patterns = [
                    r'\b' + re.escape(skill) + r'\b',
                    r'\b' + re.escape(skill.replace(' ', '')) + r'\b',
                    r'\b' + re.escape(skill.replace('.', '')) + r'\b',
                ]
                
                found = False
                for pattern in patterns:
                    if re.search(pattern, resume_lower, re.IGNORECASE):
                        if skill not in found_skills[category]:
                            found_skills[category].append(skill)
                        found = True
                        break

        # 3. USE AI FOR ENTIRE RESUME SCAN (NEW)
        if self.use_ollama:
            logger.info("🤖 Using AI to scan entire resume for hidden skills...")
            ai_skills_prompt = f"""Extract all technical skills and tools from this resume. 
            Return ONLY a comma-separated list of skills. Do not include experience or categories.
            
            Resume:
            {resume_text[:8000]}
            """
            ai_response = self._call_ollama(ai_skills_prompt, max_tokens=300)
            if ai_response:
                ai_extracted = [s.strip().lower() for s in ai_response.split(',') if len(s.strip()) > 1]
                # Map AI skills back to categories or put in 'Other'
                for skill in ai_extracted:
                    added = False
                    for category, skills_list in found_skills.items():
                        if skill in [s.lower() for s in skills_list]:
                            added = True
                            break
                    if not added:
                        if 'Other' not in found_skills:
                            found_skills['Other'] = []
                        if skill not in [s.lower() for s in found_skills['Other']]:
                            found_skills['Other'].append(skill)

        # Remove empty categories
        found_skills = {k: v for k, v in found_skills.items() if v}
        total_skills = sum(len(v) for v in found_skills.values())
        logger.info(f"✅ Found {total_skills} skills in resume")
        
        return found_skills
    
    def get_job_requirements(self, job_title: str, location: str = "India") -> Dict:
        """Get typical requirements for a job title with fallback to industry standards"""
        logger.info(f"📋 Getting requirements for {job_title}...")
        
        query = f"""
        SELECT 
            title,
            requirements,
            salary_min,
            salary_max,
            employment_type,
            experience_level
        FROM `{self.project_id}.runagen_bronze.raw_jobs`
        WHERE LOWER(title) LIKE LOWER('%{job_title}%')
            AND LOWER(location) LIKE LOWER('%{location}%')
        LIMIT 10
        """
        
        try:
            results = self.bq_client.query(query).to_dataframe()
            
            if results.empty:
                logger.warning(f"⚠️ No jobs found in BigQuery for '{job_title}', using industry-standard requirements")
                return self._get_fallback_requirements(job_title)
            
            # Extract common requirements
            all_requirements = []
            for _, row in results.iterrows():
                if row['requirements']:
                    reqs = [r.strip().lower() for r in str(row['requirements']).split(',')]
                    all_requirements.extend(reqs)
            
            # If no requirements found, use fallback
            if not all_requirements:
                logger.warning(f"⚠️ No requirements in BigQuery jobs, using industry-standard requirements")
                return self._get_fallback_requirements(job_title)
            
            # Count frequency
            req_counter = Counter(all_requirements)
            top_requirements = req_counter.most_common(15)
            
            avg_salary_min = results['salary_min'].mean()
            avg_salary_max = results['salary_max'].mean()
            
            return {
                'job_title': job_title,
                'jobs_found': len(results),
                'top_requirements': [{'skill': skill, 'frequency': count} for skill, count in top_requirements],
                'avg_salary_min': round(avg_salary_min, 2),
                'avg_salary_max': round(avg_salary_max, 2),
                'avg_salary_range': f"₹{avg_salary_min:.0f}L - ₹{avg_salary_max:.0f}L",
                'common_experience_levels': results['experience_level'].value_counts().to_dict(),
                'common_employment_types': results['employment_type'].value_counts().to_dict()
            }
        
        except Exception as e:
            logger.error(f"❌ Error getting job requirements: {e}, using fallback")
            return self._get_fallback_requirements(job_title)
    
    def _get_fallback_requirements(self, job_title: str) -> Dict:
        """Get industry-standard requirements when BigQuery is empty"""
        logger.info(f"📚 Using industry-standard requirements for {job_title}")
        
        # Industry-standard requirements by role
        role_requirements = {
            'software engineer': [
                'python', 'java', 'javascript', 'git', 'sql', 'rest api',
                'docker', 'aws', 'agile', 'testing', 'ci/cd', 'linux',
                'problem solving', 'teamwork', 'communication'
            ],
            'data scientist': [
                'python', 'machine learning', 'sql', 'statistics', 'pandas',
                'numpy', 'tensorflow', 'scikit-learn', 'data visualization',
                'jupyter', 'r', 'deep learning', 'nlp', 'big data', 'spark'
            ],
            'data engineer': [
                'python', 'sql', 'spark', 'hadoop', 'etl', 'aws', 'kafka',
                'airflow', 'docker', 'bigquery', 'data warehousing',
                'data modeling', 'postgresql', 'mongodb', 'linux'
            ],
            'data analyst': [
                'sql', 'python', 'excel', 'tableau', 'power bi', 'statistics',
                'data visualization', 'pandas', 'r', 'data analysis',
                'reporting', 'dashboards', 'business intelligence', 'analytics'
            ],
            'frontend developer': [
                'javascript', 'react', 'html', 'css', 'typescript', 'vue',
                'angular', 'responsive design', 'rest api', 'git', 'webpack',
                'testing', 'ui/ux', 'sass', 'redux'
            ],
            'backend developer': [
                'python', 'java', 'node.js', 'sql', 'rest api', 'docker',
                'aws', 'microservices', 'mongodb', 'postgresql', 'redis',
                'git', 'linux', 'api design', 'testing'
            ],
            'full stack developer': [
                'javascript', 'python', 'react', 'node.js', 'sql', 'html',
                'css', 'rest api', 'docker', 'git', 'aws', 'mongodb',
                'postgresql', 'testing', 'agile'
            ],
            'devops engineer': [
                'docker', 'kubernetes', 'aws', 'ci/cd', 'jenkins', 'terraform',
                'ansible', 'linux', 'python', 'bash', 'monitoring', 'git',
                'networking', 'security', 'automation'
            ],
            'machine learning engineer': [
                'python', 'machine learning', 'tensorflow', 'pytorch', 'deep learning',
                'nlp', 'computer vision', 'sql', 'docker', 'aws', 'mlops',
                'scikit-learn', 'pandas', 'numpy', 'git'
            ],
            'cloud engineer': [
                'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform',
                'linux', 'networking', 'security', 'python', 'bash',
                'ci/cd', 'monitoring', 'automation', 'devops'
            ]
        }
        
        # Find matching role (case-insensitive, partial match)
        job_title_lower = job_title.lower()
        requirements = []
        
        for role, reqs in role_requirements.items():
            if role in job_title_lower or job_title_lower in role:
                requirements = reqs
                break
        
        # Default to software engineer if no match
        if not requirements:
            requirements = role_requirements['software engineer']
        
        # Format as top_requirements
        top_requirements = [
            {'skill': skill, 'frequency': 10}  # Dummy frequency
            for skill in requirements
        ]
        
        return {
            'job_title': job_title,
            'jobs_found': 0,
            'top_requirements': top_requirements,
            'avg_salary_min': 600000,
            'avg_salary_max': 1200000,
            'avg_salary_range': '₹6L - ₹12L',
            'common_experience_levels': {'Mid-Level': 1},
            'common_employment_types': {'Full-time': 1},
            'source': 'industry_standards'
        }
    
    def calculate_resume_match_score(self, resume_skills: Dict[str, List[str]], 
                                    job_requirements: List[str]) -> Dict:
        """Calculate how well resume matches job requirements - Enhanced with fuzzy matching"""
        logger.info("📊 Calculating resume match score...")
        
        # Flatten resume skills
        resume_skills_flat = []
        for category_skills in resume_skills.values():
            resume_skills_flat.extend(category_skills)
        
        resume_skills_flat = [s.lower().strip() for s in resume_skills_flat]
        job_requirements = [r.lower().strip() for r in job_requirements]
        
        # Skill synonyms and variations for better matching
        skill_synonyms = {
            'javascript': ['js', 'javascript', 'ecmascript'],
            'typescript': ['ts', 'typescript'],
            'python': ['python', 'python3', 'py'],
            'node.js': ['node', 'nodejs', 'node.js'],
            'react': ['react', 'reactjs', 'react.js'],
            'angular': ['angular', 'angularjs', 'angular.js'],
            'vue': ['vue', 'vuejs', 'vue.js'],
            'machine learning': ['ml', 'machine learning', 'machinelearning'],
            'artificial intelligence': ['ai', 'artificial intelligence'],
            'sql': ['sql', 'mysql', 'postgresql', 'sql server'],
            'nosql': ['nosql', 'mongodb', 'cassandra', 'dynamodb'],
            'aws': ['aws', 'amazon web services'],
            'gcp': ['gcp', 'google cloud', 'google cloud platform'],
            'docker': ['docker', 'containerization'],
            'kubernetes': ['k8s', 'kubernetes'],
            'ci/cd': ['ci/cd', 'cicd', 'continuous integration', 'continuous deployment'],
        }
        
        # Calculate matches with fuzzy logic
        matched_skills = []
        missing_skills = []
        
        for req_skill in job_requirements:
            matched = False
            
            # Direct match
            if req_skill in resume_skills_flat:
                matched_skills.append(req_skill)
                matched = True
            else:
                # Check synonyms
                for synonym_group in skill_synonyms.values():
                    if req_skill in synonym_group:
                        # Check if any synonym is in resume
                        for synonym in synonym_group:
                            if synonym in resume_skills_flat:
                                matched_skills.append(req_skill)
                                matched = True
                                break
                    if matched:
                        break
                
                # Partial match (e.g., "python" matches "python3")
                if not matched:
                    for resume_skill in resume_skills_flat:
                        if req_skill in resume_skill or resume_skill in req_skill:
                            if len(req_skill) > 2 and len(resume_skill) > 2:  # Avoid false matches
                                matched_skills.append(req_skill)
                                matched = True
                                break
            
            if not matched:
                missing_skills.append(req_skill)
        
        match_percentage = (len(matched_skills) / len(job_requirements) * 100) if job_requirements else 0
        
        logger.info(f"   Matched: {len(matched_skills)}/{len(job_requirements)} skills ({match_percentage:.1f}%)")
        
        return {
            'match_percentage': round(match_percentage, 2),
            'matched_skills': matched_skills,
            'missing_skills': missing_skills,
            'matched_count': len(matched_skills),
            'missing_count': len(missing_skills),
            'total_required': len(job_requirements),
            'match_level': 'Excellent' if match_percentage >= 80 else 'Good' if match_percentage >= 60 else 'Fair' if match_percentage >= 40 else 'Poor'
        }
    
    def generate_optimization_suggestions(self, resume_skills: Dict[str, List[str]], 
                                         job_title: str) -> Dict:
        """Generate suggestions to optimize resume"""
        logger.info("💡 Generating optimization suggestions...")
        
        job_reqs = self.get_job_requirements(job_title)
        
        if 'error' in job_reqs or 'status' in job_reqs:
            return {'error': 'Could not fetch job requirements'}
        
        # Extract required skills from job requirements
        required_skills = [req['skill'] for req in job_reqs['top_requirements']]
        
        # Calculate match
        match_score = self.calculate_resume_match_score(resume_skills, required_skills)
        
        suggestions = {
            'job_title': job_title,
            'current_match': match_score['match_percentage'],
            'match_level': match_score['match_level'],
            'matched_skills': match_score['matched_skills'],
            'missing_skills': match_score['missing_skills'][:5],  # Top 5 missing
            'suggestions': []
        }
        
        # Generate specific suggestions
        if match_score['missing_count'] > 0:
            suggestions['suggestions'].append({
                'priority': 'HIGH',
                'action': 'Add Missing Skills',
                'details': f"Add these {match_score['missing_count']} missing skills to your resume: {', '.join(match_score['missing_skills'][:3])}",
                'impact': 'Could increase match score by 20-30%'
            })
        
        # Suggest skill development
        if match_score['missing_count'] > 0:
            suggestions['suggestions'].append({
                'priority': 'HIGH',
                'action': 'Develop Missing Skills',
                'details': f"Consider learning: {', '.join(match_score['missing_skills'][:3])}",
                'impact': 'Significantly improve job prospects'
            })
        
        # Suggest highlighting existing skills
        if match_score['matched_count'] > 0:
            suggestions['suggestions'].append({
                'priority': 'MEDIUM',
                'action': 'Highlight Matching Skills',
                'details': f"Emphasize these {match_score['matched_count']} matching skills in your resume",
                'impact': 'Improve ATS (Applicant Tracking System) score'
            })
        
        # Suggest salary expectations
        if 'avg_salary_range' in job_reqs:
            suggestions['suggestions'].append({
                'priority': 'MEDIUM',
                'action': 'Set Salary Expectations',
                'details': f"Average salary for {job_title}: {job_reqs['avg_salary_range']}",
                'impact': 'Help with salary negotiation'
            })
        
        # Suggest experience level
        if 'common_experience_levels' in job_reqs:
            exp_levels = job_reqs['common_experience_levels']
            most_common = max(exp_levels, key=exp_levels.get) if exp_levels else 'Not specified'
            suggestions['suggestions'].append({
                'priority': 'LOW',
                'action': 'Match Experience Level',
                'details': f"Most common experience level: {most_common}",
                'impact': 'Better alignment with job market'
            })
        
        return suggestions
    
    def optimize_resume_for_role(self, resume_text: str, target_role: str) -> Dict:
        """Complete ATS-focused resume optimization for a target role"""
        logger.info(f"🎯 ATS Optimizing resume for {target_role}...")
        
        # 1. Extract skills from ENTIRE resume
        resume_skills = self.extract_skills_from_resume(resume_text)
        
        # 2. Get job requirements
        job_reqs = self.get_job_requirements(target_role)
        
        if 'error' in job_reqs or 'status' in job_reqs:
            return {'error': 'Could not fetch job requirements'}
        
        # 3. Calculate match
        required_skills = [req['skill'] for req in job_reqs['top_requirements']]
        match_score = self.calculate_resume_match_score(resume_skills, required_skills)
        
        # 4. Comprehensive ATS Analysis
        ats_analysis = self._analyze_ats_compatibility(resume_text, required_skills)
        ats_analysis['has_matching_job_title'] = target_role.lower() in resume_text.lower()
        
        # 5. Generate Optimization Suggestions
        suggestions = []
        
        # Critical Keywords
        if match_score['missing_skills']:
            missing_top = match_score['missing_skills'][:5]
            suggestions.append({
                'priority': 'CRITICAL',
                'category': 'ATS Keywords',
                'action': 'Add Missing Keywords',
                'details': f"ATS systems scan for these keywords: {', '.join(missing_top)}. Add them to your Skills section and work experience descriptions.",
                'impact': 'Increases ATS pass rate by 40-60%',
                'how_to_fix': [f"Add '{s}' to your Skills section" for s in missing_top[:3]]
            })
        
        # Formatting & Sections
        if not ats_analysis['has_standard_sections']:
            suggestions.append({
                'priority': 'HIGH',
                'category': 'ATS Section Headers',
                'action': 'Use Standard Section Headers',
                'details': "ATS systems look for standard headers like 'EXPERIENCE', 'SKILLS', 'EDUCATION'.",
                'impact': 'Ensures ATS can parse your resume correctly',
                'how_to_fix': ["Use 'WORK EXPERIENCE' instead of creative titles"]
            })
        
        # AI-Powered Personalized Suggestions (scanning entire resume)
        ats_score = self._calculate_ats_score(ats_analysis, match_score)
        ai_suggestions = self._generate_ai_suggestions(
            resume_text, 
            target_role, 
            match_score['missing_skills'][:5],
            ats_score
        )
        if ai_suggestions:
            suggestions.extend(ai_suggestions)

        # AI Holistic Review
        holistic_review = self._get_ai_holistic_review(resume_text, target_role)
        
        optimization_report = {
            'target_role': target_role,
            'ats_score': {
                'overall_score': ats_score,
                'rating': 'Excellent' if ats_score >= 80 else 'Good' if ats_score >= 60 else 'Fair' if ats_score >= 40 else 'Poor',
                'keyword_match': match_score['match_percentage'],
                'formatting_score': ats_analysis['formatting_score'],
                'pass_probability': f"{min(95, ats_score)}%"
            },
            'current_status': {
                'skills_found': sum(len(v) for v in resume_skills.values()),
                'keywords_matched': match_score['matched_count'],
                'keywords_missing': match_score['missing_count'],
                'ats_compatible': ats_score >= 60
            },
            'holistic_review': holistic_review,
            'optimization_suggestions': suggestions,
            'quick_wins': [s for s in suggestions if s['priority'] in ['CRITICAL', 'HIGH']][:3],
            'ats_checklist': {
                'keyword_optimization': match_score['match_percentage'] >= 70,
                'standard_sections': ats_analysis['has_standard_sections'],
                'simple_formatting': True,
                'quantifiable_results': ats_analysis['has_numbers'] >= 3,
                'action_verbs': ats_analysis['has_action_verbs'],
                'job_title_match': ats_analysis['has_matching_job_title']
            }
        }
        
        logger.info(f"✅ ATS Score: {ats_score}/100")
        return optimization_report

    def _get_ai_holistic_review(self, resume_text: str, target_role: str) -> str:
        """Get a holistic qualitative review of the resume from the AI"""
        if not self.use_ollama:
            return "AI Holistic Review unavailable. Please ensure Ollama is running."

        prompt = f"""You are a senior hiring manager for a {target_role} position. 
        Analyze this ENTIRE resume and provide a 3-paragraph executive summary:
        1. Overall impression and professional tone.
        2. Strongest points and areas of brilliance.
        3. Critical gaps or reasons why you might hesitate to hire this person.

        Resume Text:
        {resume_text[:10000]}

        Target Role: {target_role}
        """
        
        logger.info("🤖 Generating AI Holistic Review...")
        return self._call_ollama(prompt, max_tokens=1000)

    def _generate_ai_suggestions(self, resume_text: str, target_role: str, 
                                 missing_skills: List[str], ats_score: int) -> List[Dict]:
        """Generate AI-powered personalized suggestions using Ollama - Scanning entire resume"""
        if not self.use_ollama:
            return []
        
        logger.info("🤖 Generating AI-powered suggestions with Ollama (Full Scan)...")
        
        # Create a more detailed prompt for Ollama scanning the entire resume
        prompt = f"""You are an expert resume consultant. Analyze this FULL resume for a {target_role} position.

Full Resume Text:
{resume_text[:10000]}

Target Role: {target_role}
Current ATS Score: {ats_score}/100
Missing Top Skills: {', '.join(missing_skills)}

Task: Provide 3-4 HIGH-IMPACT, SPECIFIC suggestions to optimize this resume. 
For each suggestion, identify a specific bullet point or section and provide a REWRITTEN version that is more impactful.

You MUST return your response as a valid JSON array of objects, wrapped in ```json code blocks.
Example format:
```json
[
  {{
    "priority": "HIGH",
    "category": "Content Optimization",
    "action": "Rewrite Experience Bullet",
    "details": "The current bullet point for X is weak.",
    "impact": "Improves impact score",
    "how_to_fix": ["Original: ...", "Revised: ..."]
  }}
]
```

Return ONLY the JSON. Do not include any other conversational text."""

        try:
            response = self._call_ollama(prompt, max_tokens=1500)
            
            if not response:
                return []
            
            # 1. Clean response (remove markdown and preamble)
            cleaned_response = response.strip()
            
            # 2. Try to extract JSON array using multiple patterns
            json_content = ""
            patterns = [
                r'```json\s*(\[.*?\])\s*```',      # JSON code block with array
                r'```\s*(\[.*?\])\s*```',          # Any code block with array
                r'(\[.*?\])',                      # Just the array
            ]
            
            for pattern in patterns:
                match = re.search(pattern, cleaned_response, re.DOTALL)
                if match:
                    json_content = match.group(1 if '```' in pattern else 0).strip()
                    try:
                        ai_suggestions = json.loads(json_content)
                        if isinstance(ai_suggestions, list):
                            for s in ai_suggestions:
                                s['ai_generated'] = True
                            return ai_suggestions
                    except json.JSONDecodeError:
                        continue
            
            # 3. Fallback to flexible manual parsing if JSON fails
            logger.warning("⚠️ AI Suggestion parsing failed, using flexible manual parser")
            ai_suggestions = []
            
            # Look for suggestion blocks (Suggestion 1:, 1., etc)
            blocks = re.split(r'(?i)suggestion\s*\d+:|###|##|\n\d+\.', cleaned_response)
            for block in blocks:
                if len(block.strip()) < 20: continue
                
                # Try to extract action and details
                action_match = re.search(r'(?i)action:\s*(.+)', block)
                details_match = re.search(r'(?i)details:\s*(.+)', block)
                
                if action_match:
                    ai_suggestions.append({
                        'priority': 'HIGH',
                        'category': 'AI Suggestion',
                        'action': action_match.group(1).strip(),
                        'details': details_match.group(1).strip() if details_match else block.strip()[:200],
                        'impact': 'Significantly improves resume quality',
                        'how_to_fix': ['Follow AI recommendation'],
                        'ai_generated': True
                    })
            
            if not ai_suggestions:
                # Last resort: just split by double newline
                for para in cleaned_response.split('\n\n'):
                    if len(para.strip()) > 50:
                        ai_suggestions.append({
                            'priority': 'MEDIUM',
                            'category': 'AI Review',
                            'action': 'Optimize Content',
                            'details': para.strip()[:300],
                            'impact': 'Improves professional tone',
                            'how_to_fix': ['Review AI comments'],
                            'ai_generated': True
                        })
            
            return ai_suggestions[:4]
            
        except Exception as e:
            logger.error(f"❌ Error generating AI suggestions: {e}")
            return []
    
    def _analyze_ats_compatibility(self, resume_text: str, required_skills: List[str]) -> Dict:
        """Comprehensive analysis of ENTIRE resume for ATS compatibility"""
        logger.info("🔍 Performing comprehensive resume analysis...")
        
        analysis = {}
        resume_lower = resume_text.lower()
        
        # ===== 1. SECTION ANALYSIS =====
        logger.info("   Analyzing resume sections...")
        
        # Check for all important sections
        sections = {
            'contact': ['email', 'phone', 'linkedin', 'github', '@'],
            'summary': ['summary', 'objective', 'profile', 'about'],
            'experience': ['experience', 'work history', 'employment', 'professional experience'],
            'education': ['education', 'academic', 'degree', 'university', 'college'],
            'skills': ['skills', 'technical skills', 'competencies', 'expertise'],
            'projects': ['projects', 'portfolio', 'work samples'],
            'certifications': ['certifications', 'certificates', 'licenses'],
            'achievements': ['achievements', 'awards', 'accomplishments', 'honors']
        }
        
        found_sections = {}
        for section_name, keywords in sections.items():
            found_sections[section_name] = any(kw in resume_lower for kw in keywords)
        
        analysis['sections_found'] = found_sections
        analysis['section_count'] = sum(found_sections.values())
        analysis['has_standard_sections'] = found_sections['experience'] and found_sections['skills'] and found_sections['education']
        
        # ===== 2. WORK EXPERIENCE ANALYSIS =====
        logger.info("   Analyzing work experience...")
        
        # Count job positions using multiple indicators
        job_positions = 0
        
        # Method 1: Date patterns (various formats)
        date_patterns = [
            r'\b(19|20)\d{2}\s*[-–—]\s*(19|20)\d{2}\b',  # 2020-2023, 2020–2023
            r'\b(19|20)\d{2}\s*[-–—]\s*(present|current|now)\b',  # 2020-Present
            r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(19|20)\d{2}\s*[-–—]\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(19|20)\d{2}\b',  # Jan 2020 - Dec 2023
            r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(19|20)\d{2}\s*[-–—]\s*(present|current|now)\b',  # Jan 2020 - Present
            r'\b(19|20)\d{2}\s*[-–—]\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(19|20)\d{2}\b',  # 2020 - Dec 2023
            r'\b\d{1,2}/\d{4}\s*[-–—]\s*\d{1,2}/\d{4}\b',  # 01/2020 - 12/2023
            r'\b\d{1,2}/\d{4}\s*[-–—]\s*(present|current|now)\b',  # 01/2020 - Present
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, resume_lower, re.IGNORECASE)
            job_positions += len(matches)
        
        # Method 2: Job title indicators (if dates not found)
        if job_positions == 0:
            job_title_patterns = [
                r'(software engineer|developer|analyst|manager|lead|senior|junior|intern)',
                r'(engineer|architect|consultant|specialist|coordinator|administrator)',
                r'(designer|programmer|scientist|researcher|technician)'
            ]
            
            for pattern in job_title_patterns:
                matches = re.findall(pattern, resume_lower, re.IGNORECASE)
                # Count unique job titles (avoid duplicates)
                job_positions = max(job_positions, len(set(matches)))
        
        # Method 3: Company indicators
        company_indicators = ['pvt', 'ltd', 'inc', 'llc', 'corporation', 'company', 'technologies', 'solutions']
        company_count = 0
        for indicator in company_indicators:
            if indicator in resume_lower:
                company_count += resume_lower.count(indicator)
        
        # Use company count as additional signal
        if company_count > 0 and job_positions == 0:
            job_positions = min(company_count, 5)  # Cap at 5
        
        analysis['job_positions_count'] = job_positions
        analysis['has_work_experience'] = job_positions > 0
        
        # ===== 3. ACTION VERBS ANALYSIS =====
        logger.info("   Analyzing action verbs...")
        
        action_verbs = [
            'achieved', 'administered', 'analyzed', 'architected', 'automated',
            'built', 'collaborated', 'created', 'delivered', 'designed',
            'developed', 'directed', 'drove', 'enhanced', 'established',
            'executed', 'generated', 'implemented', 'improved', 'increased',
            'initiated', 'launched', 'led', 'managed', 'optimized',
            'orchestrated', 'organized', 'pioneered', 'planned', 'produced',
            'reduced', 'redesigned', 'resolved', 'spearheaded', 'streamlined',
            'transformed', 'upgraded'
        ]
        
        found_action_verbs = []
        for verb in action_verbs:
            if re.search(r'\b' + verb + r'\b', resume_lower):
                found_action_verbs.append(verb)
        
        analysis['action_verbs_count'] = len(found_action_verbs)
        analysis['action_verbs_found'] = found_action_verbs[:10]  # Top 10
        analysis['has_action_verbs'] = len(found_action_verbs) >= 3
        
        # ===== 4. QUANTIFIABLE ACHIEVEMENTS =====
        logger.info("   Analyzing quantifiable achievements...")
        
        # Find numbers, percentages, dollar amounts, metrics
        metrics_patterns = [
            r'\d+%',  # Percentages: 50%
            r'\$\d+[kmb]?',  # Dollar amounts: $50K, $1M
            r'\d+\+?\s*(years?|months?|weeks?)',  # Time: 5 years, 3+ months
            r'\d+\+?\s*(users?|customers?|clients?)',  # Scale: 1000+ users
            r'\d+x',  # Multipliers: 2x, 10x
            r'\d+\s*(million|thousand|billion)',  # Large numbers
            r'increased?\s+by\s+\d+',  # Increased by 50
            r'reduced?\s+by\s+\d+',  # Reduced by 30
            r'improved?\s+by\s+\d+',  # Improved by 40
        ]
        
        all_metrics = []
        for pattern in metrics_patterns:
            matches = re.findall(pattern, resume_lower, re.IGNORECASE)
            all_metrics.extend(matches)
        
        analysis['metrics_count'] = len(all_metrics)
        analysis['has_numbers'] = len(all_metrics)
        analysis['has_quantifiable_results'] = len(all_metrics) >= 5
        
        # ===== 5. KEYWORD DENSITY ANALYSIS =====
        logger.info("   Analyzing keyword density...")
        
        keyword_counts = []
        keyword_details = {}
        for skill in required_skills[:15]:  # Check top 15 required skills
            count = resume_lower.count(skill.lower())
            keyword_counts.append(count)
            if count > 0:
                keyword_details[skill] = count
        
        analysis['keyword_density'] = sum(keyword_counts) / len(keyword_counts) if keyword_counts else 0
        analysis['keyword_details'] = keyword_details
        analysis['keywords_mentioned'] = len([c for c in keyword_counts if c > 0])
        
        # ===== 6. EDUCATION ANALYSIS =====
        logger.info("   Analyzing education...")
        
        education_keywords = [
            'bachelor', 'master', 'phd', 'doctorate', 'mba', 'degree',
            'b.s', 'b.a', 'm.s', 'm.a', 'b.tech', 'm.tech', 'b.e', 'm.e',
            'university', 'college', 'institute'
        ]
        
        education_found = []
        for keyword in education_keywords:
            if re.search(r'\b' + keyword + r'\b', resume_lower):
                education_found.append(keyword)
        
        analysis['education_keywords_count'] = len(education_found)
        analysis['has_education'] = len(education_found) > 0
        
        # ===== 7. PROJECTS ANALYSIS =====
        logger.info("   Analyzing projects...")
        
        # Look for project indicators
        project_indicators = [
            'project', 'developed', 'built', 'created', 'implemented',
            'github', 'portfolio', 'demo', 'repository'
        ]
        
        project_mentions = 0
        for indicator in project_indicators:
            project_mentions += len(re.findall(r'\b' + indicator + r'\b', resume_lower))
        
        analysis['project_mentions'] = project_mentions
        analysis['has_projects'] = project_mentions >= 3
        
        # ===== 8. CERTIFICATIONS & ACHIEVEMENTS ANALYSIS =====
        logger.info("   Analyzing certifications and achievements...")
        
        # Professional Certifications (Real certifications that add value)
        professional_certs = {
            'cloud': ['aws certified', 'azure certified', 'gcp certified', 'google cloud certified'],
            'project_management': ['pmp', 'prince2', 'capm', 'csm', 'psm'],
            'agile': ['scrum master', 'scrum product owner', 'safe', 'agile certified'],
            'security': ['cissp', 'ceh', 'comptia security+', 'cism', 'cisa'],
            'networking': ['ccna', 'ccnp', 'comptia network+'],
            'database': ['oracle certified', 'mongodb certified', 'mysql certified'],
            'programming': ['oracle certified java', 'microsoft certified', 'red hat certified'],
            'data': ['databricks certified', 'snowflake certified', 'tableau certified']
        }
        
        # Competitions & Hackathons (Good but not certifications)
        competitions = [
            'hackathon', 'imagine cup', 'code jam', 'kaggle competition',
            'coding competition', 'programming contest', 'tech challenge',
            'innovation challenge', 'startup competition'
        ]
        
        # Online Courses (Learning but not professional certifications)
        online_courses = [
            'coursera', 'udemy', 'edx', 'udacity', 'pluralsight',
            'linkedin learning', 'datacamp', 'codecademy'
        ]
        
        # Count professional certifications
        prof_cert_count = 0
        found_prof_certs = []
        for category, certs in professional_certs.items():
            for cert in certs:
                if cert in resume_lower:
                    prof_cert_count += 1
                    found_prof_certs.append(cert)
        
        # Count competitions/hackathons
        competition_count = 0
        found_competitions = []
        for comp in competitions:
            matches = re.findall(r'\b' + re.escape(comp) + r'\b', resume_lower, re.IGNORECASE)
            if matches:
                competition_count += len(matches)
                found_competitions.append(comp)
        
        # Count online courses
        course_count = 0
        found_courses = []
        for course in online_courses:
            if course in resume_lower:
                course_count += 1
                found_courses.append(course)
        
        # Generic certification keywords (fallback)
        generic_cert_keywords = ['certified', 'certification', 'certificate', 'license']
        generic_cert_count = 0
        for keyword in generic_cert_keywords:
            generic_cert_count += len(re.findall(r'\b' + keyword + r'\b', resume_lower))
        
        # Store detailed breakdown
        analysis['professional_certifications'] = {
            'count': prof_cert_count,
            'found': found_prof_certs[:5]  # Top 5
        }
        analysis['competitions_hackathons'] = {
            'count': competition_count,
            'found': found_competitions[:5]  # Top 5
        }
        analysis['online_courses'] = {
            'count': course_count,
            'found': found_courses[:5]  # Top 5
        }
        
        # Overall certification metrics
        analysis['certification_mentions'] = generic_cert_count
        analysis['has_certifications'] = prof_cert_count >= 1  # At least 1 professional cert
        analysis['has_competitions'] = competition_count >= 1
        analysis['has_courses'] = course_count >= 1
        
        # Total achievements (certs + competitions + courses)
        analysis['total_achievements'] = prof_cert_count + competition_count + course_count
        
        # ===== 9. RESUME LENGTH ANALYSIS =====
        logger.info("   Analyzing resume length...")
        
        word_count = len(resume_text.split())
        char_count = len(resume_text)
        line_count = len(resume_text.split('\n'))
        
        analysis['word_count'] = word_count
        analysis['char_count'] = char_count
        analysis['line_count'] = line_count
        analysis['appropriate_length'] = 300 <= word_count <= 1500  # Ideal resume length
        
        # ===== 10. CONTACT INFORMATION =====
        logger.info("   Analyzing contact information...")
        
        has_email = bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', resume_text))
        has_phone = bool(re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', resume_text))
        has_linkedin = 'linkedin' in resume_lower
        has_github = 'github' in resume_lower
        
        analysis['has_email'] = has_email
        analysis['has_phone'] = has_phone
        analysis['has_linkedin'] = has_linkedin
        analysis['has_github'] = has_github
        analysis['contact_info_complete'] = has_email and has_phone
        
        # ===== 11. JOB TITLE MATCHING =====
        # This will be set by the calling function based on target_role
        analysis['has_matching_job_title'] = False  # Default, will be updated
        
        # ===== 12. CALCULATE COMPREHENSIVE FORMATTING SCORE =====
        logger.info("   Calculating formatting score...")
        
        formatting_score = 0
        
        # Section completeness (30 points)
        if analysis['section_count'] >= 5:
            formatting_score += 30
        elif analysis['section_count'] >= 3:
            formatting_score += 20
        else:
            formatting_score += 10
        
        # Action verbs (15 points)
        if analysis['action_verbs_count'] >= 10:
            formatting_score += 15
        elif analysis['action_verbs_count'] >= 5:
            formatting_score += 10
        elif analysis['action_verbs_count'] >= 3:
            formatting_score += 5
        
        # Quantifiable results (25 points)
        if analysis['metrics_count'] >= 10:
            formatting_score += 25
        elif analysis['metrics_count'] >= 5:
            formatting_score += 15
        elif analysis['metrics_count'] >= 3:
            formatting_score += 10
        
        # Keyword density (15 points)
        if analysis['keyword_density'] >= 2:
            formatting_score += 15
        elif analysis['keyword_density'] >= 1:
            formatting_score += 10
        elif analysis['keyword_density'] >= 0.5:
            formatting_score += 5
        
        # Resume length (10 points)
        if analysis['appropriate_length']:
            formatting_score += 10
        
        # Contact info (5 points)
        if analysis['contact_info_complete']:
            formatting_score += 5
        
        analysis['formatting_score'] = min(100, formatting_score)
        
        # ===== SUMMARY LOG =====
        logger.info(f"   ✓ Comprehensive Analysis Complete:")
        logger.info(f"      - Sections: {analysis['section_count']}/8")
        logger.info(f"      - Work Experience: {analysis['job_positions_count']} positions")
        logger.info(f"      - Action Verbs: {analysis['action_verbs_count']}")
        logger.info(f"      - Metrics: {analysis['metrics_count']}")
        logger.info(f"      - Keywords: {analysis['keywords_mentioned']}/{len(required_skills[:15])}")
        logger.info(f"      - Professional Certifications: {analysis['professional_certifications']['count']}")
        logger.info(f"      - Competitions/Hackathons: {analysis['competitions_hackathons']['count']}")
        logger.info(f"      - Online Courses: {analysis['online_courses']['count']}")
        logger.info(f"      - Word Count: {analysis['word_count']}")
        logger.info(f"      - Formatting Score: {analysis['formatting_score']}/100")
        
        return analysis
    
    def _calculate_ats_score(self, ats_analysis: Dict, match_score: Dict) -> int:
        """Calculate overall ATS compatibility score - Enhanced"""
        score = 0
        
        # Keyword match (35% weight) - Slightly reduced to balance other factors
        keyword_score = match_score['match_percentage']
        score += keyword_score * 0.35
        
        # Formatting (25% weight)
        score += ats_analysis['formatting_score'] * 0.25
        
        # Keyword density (20% weight) - Increased importance
        density_score = min(100, ats_analysis['keyword_density'] * 50)
        score += density_score * 0.20
        
        # Numbers/metrics (10% weight)
        numbers_score = min(100, ats_analysis['has_numbers'] * 20)
        score += numbers_score * 0.10
        
        # Resume completeness bonus (10% weight)
        # Check if resume has key sections
        completeness_score = 0
        if ats_analysis.get('has_standard_sections', False):
            completeness_score += 40
        if ats_analysis.get('has_action_verbs', False):
            completeness_score += 30
        if ats_analysis.get('has_numbers', 0) >= 3:
            completeness_score += 30
        
        score += completeness_score * 0.10
        
        # Ensure score is between 0-100
        final_score = max(0, min(100, int(score)))
        
        logger.info(f"   ATS Score Breakdown:")
        logger.info(f"   - Keyword Match: {keyword_score:.1f}% (weight: 35%)")
        logger.info(f"   - Formatting: {ats_analysis['formatting_score']:.1f}% (weight: 25%)")
        logger.info(f"   - Keyword Density: {density_score:.1f}% (weight: 20%)")
        logger.info(f"   - Metrics/Numbers: {numbers_score:.1f}% (weight: 10%)")
        logger.info(f"   - Completeness: {completeness_score:.1f}% (weight: 10%)")
        logger.info(f"   = Final Score: {final_score}/100")
        
        return final_score
    
    def _create_action_plan(self, missing_skills: List[str], target_role: str) -> List[Dict]:
        """Create a detailed action plan to improve resume"""
        action_plan = []
        
        for i, skill in enumerate(missing_skills[:5], 1):
            action_plan.append({
                'step': i,
                'skill': skill,
                'timeline': f"Week {i*2}-{i*2+2}",
                'resources': [
                    f"Online course on {skill}",
                    f"Practice projects using {skill}",
                    f"Build portfolio with {skill}"
                ],
                'success_criteria': f"Complete 1-2 projects using {skill}"
            })
        
        return action_plan
    
    def compare_resumes(self, resume1_text: str, resume2_text: str, job_title: str) -> Dict:
        """Compare two resumes for a job"""
        logger.info("🔄 Comparing two resumes...")
        
        # Extract skills from both resumes
        skills1 = self.extract_skills_from_resume(resume1_text)
        skills2 = self.extract_skills_from_resume(resume2_text)
        
        # Get job requirements
        job_reqs = self.get_job_requirements(job_title)
        
        if 'error' in job_reqs or 'status' in job_reqs:
            return {'error': 'Could not fetch job requirements'}
        
        required_skills = [req['skill'] for req in job_reqs['top_requirements']]
        
        # Calculate match scores
        match1 = self.calculate_resume_match_score(skills1, required_skills)
        match2 = self.calculate_resume_match_score(skills2, required_skills)
        
        comparison = {
            'job_title': job_title,
            'resume1': {
                'skills_count': sum(len(v) for v in skills1.values()),
                'match_percentage': match1['match_percentage'],
                'match_level': match1['match_level'],
                'matched_skills': match1['matched_skills'],
                'missing_skills': match1['missing_skills']
            },
            'resume2': {
                'skills_count': sum(len(v) for v in skills2.values()),
                'match_percentage': match2['match_percentage'],
                'match_level': match2['match_level'],
                'matched_skills': match2['matched_skills'],
                'missing_skills': match2['missing_skills']
            },
            'winner': 'Resume 1' if match1['match_percentage'] > match2['match_percentage'] else 'Resume 2' if match2['match_percentage'] > match1['match_percentage'] else 'Tie',
            'difference': abs(match1['match_percentage'] - match2['match_percentage'])
        }
        
        return comparison


def main():
    """Main execution"""
    print("\n" + "="*70)
    print("🚀 Phase 6: Resume Optimization Engine")
    print("="*70 + "\n")
    
    optimizer = ResumeOptimizer()
    
    # Sample resume text
    sample_resume = """
    John Doe
    Data Analyst | Python | SQL | Tableau
    
    Skills:
    - Python, SQL, R
    - Tableau, Power BI
    - Excel, Google Sheets
    - Data Analysis, Statistical Analysis
    - Machine Learning basics
    
    Experience:
    - 3 years as Data Analyst
    - Worked with BigQuery, PostgreSQL
    - Created dashboards and reports
    """
    
    # Optimize for Data Analyst role
    print("📋 Optimizing resume for Data Analyst role...")
    print("-"*70)
    
    optimization = optimizer.optimize_resume_for_role(sample_resume, "Data Analyst")
    
    print(f"\n✅ Current Match: {optimization['current_status']['match_percentage']}%")
    print(f"📈 Potential Match: {optimization['improvement_potential']['potential_match_percentage']}%")
    print(f"⏱️  Time to Improve: {optimization['improvement_potential']['estimated_time_to_improve']}")
    
    print("\n💡 Top Suggestions:")
    for i, suggestion in enumerate(optimization['optimization_suggestions'][:3], 1):
        print(f"{i}. [{suggestion['priority']}] {suggestion['action']}")
        print(f"   {suggestion['details']}")
    
    print("\n📋 Action Plan:")
    for step in optimization['action_plan'][:3]:
        print(f"Step {step['step']}: Learn {step['skill']} ({step['timeline']})")
    
    print("\n" + "="*70)
    print("✅ Phase 6 Complete!")
    print("="*70 + "\n")
    
    return optimization


if __name__ == "__main__":
    main()
