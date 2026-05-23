"""
Train ML Models from Job Postings Data
Uses cleaned BigQuery job data to train career and salary prediction models
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
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, classification_report, mean_absolute_error, r2_score
import joblib
import logging
import re

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobBasedModelTrainer:
    """Train models using job postings data from BigQuery"""
    
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
        self.models_dir = Path('models')
        self.models_dir.mkdir(exist_ok=True)
    
    def extract_experience_from_title(self, title):
        """Extract years of experience from job title"""
        if not isinstance(title, str):
            return 0
        
        # Patterns: "5+ years", "3-5 years", "5 YoE", "Senior" (5+), "Junior" (0-2)
        patterns = [
            r'(\d+)\+?\s*(?:years?|yrs?|yoe)',
            r'(\d+)\s*-\s*\d+\s*(?:years?|yrs?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title.lower())
            if match:
                return int(match.group(1))
        
        # Seniority levels
        title_lower = title.lower()
        if 'senior' in title_lower or 'lead' in title_lower or 'principal' in title_lower:
            return 5
        elif 'junior' in title_lower or 'entry' in title_lower or 'fresher' in title_lower:
            return 1
        elif 'mid' in title_lower or 'intermediate' in title_lower:
            return 3
        
        return 2  # Default mid-level
    
    def categorize_role(self, title):
        """Categorize job title into role"""
        if not isinstance(title, str):
            return 'Other'
        
        title_lower = title.lower()
        
        if 'data scientist' in title_lower:
            return 'Data Scientist'
        elif 'data engineer' in title_lower:
            return 'Data Engineer'
        elif 'data analyst' in title_lower:
            return 'Data Analyst'
        elif 'machine learning' in title_lower or 'ml engineer' in title_lower or 'ai engineer' in title_lower:
            return 'ML Engineer'
        elif 'backend' in title_lower or 'back end' in title_lower or 'back-end' in title_lower:
            return 'Backend Developer'
        elif 'frontend' in title_lower or 'front end' in title_lower or 'front-end' in title_lower:
            return 'Frontend Developer'
        elif 'full stack' in title_lower or 'fullstack' in title_lower or 'full-stack' in title_lower:
            return 'Full Stack Developer'
        elif 'devops' in title_lower or 'sre' in title_lower:
            return 'DevOps Engineer'
        elif 'software engineer' in title_lower or 'software developer' in title_lower:
            return 'Software Engineer'
        elif 'product manager' in title_lower or ' pm ' in title_lower:
            return 'Product Manager'
        elif 'qa' in title_lower or 'test' in title_lower or 'quality' in title_lower:
            return 'QA Engineer'
        else:
            return 'Other'
    
    def load_training_data(self):
        """Load and preprocess job data from BigQuery"""
        logger.info("📊 Loading job data from BigQuery...")
        
        query = f"""
        SELECT 
            job_id,
            title,
            company,
            location,
            description,
            requirements,
            salary_min,
            salary_max,
            category
        FROM `{self.project_id}.runagen_bronze.raw_jobs`
        WHERE requirements IS NOT NULL 
            AND requirements != ''
            AND salary_min > 0
            AND salary_max > 0
        LIMIT 20000
        """
        
        try:
            df = self.bq_client.query(query).to_dataframe()
            
            if df.empty:
                logger.error("❌ No training data found in BigQuery!")
                return None
            
            logger.info(f"✅ Loaded {len(df)} job records")
            
            # Extract features
            logger.info("🔧 Engineering features from job data...")
            
            # Extract role category
            df['role'] = df['title'].apply(self.categorize_role)
            
            # Extract experience from title
            df['experience_years'] = df['title'].apply(self.extract_experience_from_title)
            
            # Calculate average salary
            df['avg_salary'] = (df['salary_min'] + df['salary_max']) / 2
            
            # Count skills
            df['skill_count'] = df['requirements'].str.split(',').str.len()
            
            # Check for specific skills
            df['has_python'] = df['requirements'].str.lower().str.contains('python').astype(int)
            df['has_java'] = df['requirements'].str.lower().str.contains('java').astype(int)
            df['has_javascript'] = df['requirements'].str.lower().str.contains('javascript').astype(int)
            df['has_sql'] = df['requirements'].str.lower().str.contains('sql|mysql|postgresql').astype(int)
            df['has_aws'] = df['requirements'].str.lower().str.contains('aws').astype(int)
            df['has_azure'] = df['requirements'].str.lower().str.contains('azure').astype(int)
            df['has_docker'] = df['requirements'].str.lower().str.contains('docker').astype(int)
            df['has_kubernetes'] = df['requirements'].str.lower().str.contains('kubernetes|k8s').astype(int)
            df['has_react'] = df['requirements'].str.lower().str.contains('react').astype(int)
            df['has_angular'] = df['requirements'].str.lower().str.contains('angular').astype(int)
            df['has_ml'] = df['requirements'].str.lower().str.contains('machine learning|tensorflow|pytorch').astype(int)
            df['has_spark'] = df['requirements'].str.lower().str.contains('spark').astype(int)
            df['has_kafka'] = df['requirements'].str.lower().str.contains('kafka').astype(int)
            
            # Location features
            df['is_bangalore'] = df['location'].str.lower().str.contains('bangalore|bengaluru').astype(int)
            df['is_hyderabad'] = df['location'].str.lower().str.contains('hyderabad').astype(int)
            df['is_pune'] = df['location'].str.lower().str.contains('pune').astype(int)
            df['is_mumbai'] = df['location'].str.lower().str.contains('mumbai').astype(int)
            df['is_delhi'] = df['location'].str.lower().str.contains('delhi|gurgaon|noida').astype(int)
            
            # Description length
            df['description_length'] = df['description'].str.len()
            df['requirements_length'] = df['requirements'].str.len()
            
            # Remove rows with 'Other' role (too generic)
            df = df[df['role'] != 'Other']
            
            logger.info(f"✅ After filtering: {len(df)} records with categorized roles")
            logger.info(f"\n   Role Distribution:")
            role_counts = df['role'].value_counts()
            for role, count in role_counts.items():
                logger.info(f"      {role}: {count}")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Error loading training data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def engineer_features(self, df):
        """Select features for training"""
        feature_columns = [
            'experience_years',
            'skill_count',
            'has_python',
            'has_java',
            'has_javascript',
            'has_sql',
            'has_aws',
            'has_azure',
            'has_docker',
            'has_kubernetes',
            'has_react',
            'has_angular',
            'has_ml',
            'has_spark',
            'has_kafka',
            'is_bangalore',
            'is_hyderabad',
            'is_pune',
            'is_mumbai',
            'is_delhi',
            'description_length',
            'requirements_length',
        ]
        
        features = df[feature_columns].copy()
        features = features.fillna(0)
        
        return features
    
    def train_career_model(self, df, features):
        """Train career prediction model"""
        logger.info("\n🎯 Training Career Prediction Model...")
        logger.info("="*70)
        
        X = features
        y = df['role']
        
        # Encode labels
        le = LabelEncoder()
        y_encoded = le.fit_transform(y)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train with regularization
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1
        )
        
        # Cross-validation
        logger.info("   Performing 5-fold cross-validation...")
        cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5, scoring='accuracy')
        logger.info(f"   CV Accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")
        
        # Train final model
        model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        
        logger.info(f"\n   Test Accuracy: {accuracy:.4f}")
        logger.info(f"\n   Classification Report:")
        print(classification_report(y_test, y_pred, target_names=le.classes_))
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': X.columns,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        logger.info("\n   Top 10 Important Features:")
        for _, row in feature_importance.head(10).iterrows():
            logger.info(f"      {row['feature']}: {row['importance']:.4f}")
        
        # Save model
        joblib.dump(model, self.models_dir / 'career_model_jobs.pkl')
        joblib.dump(scaler, self.models_dir / 'career_scaler_jobs.pkl')
        joblib.dump(le, self.models_dir / 'career_encoder_jobs.pkl')
        
        logger.info("\n   ✅ Career model saved!")
        
        return model, scaler, le, accuracy
    
    def train_salary_model(self, df, features):
        """Train salary prediction model"""
        logger.info("\n💰 Training Salary Prediction Model...")
        logger.info("="*70)
        
        X = features
        y = df['avg_salary']
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train with regularization
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1
        )
        
        # Cross-validation
        logger.info("   Performing 5-fold cross-validation...")
        cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5, scoring='r2')
        logger.info(f"   CV R² Score: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")
        
        # Train final model
        model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = model.predict(X_test_scaled)
        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        
        logger.info(f"\n   Test R² Score: {r2:.4f}")
        logger.info(f"   Mean Absolute Error: ₹{mae:,.0f}")
        
        # Sample predictions
        logger.info("\n   Sample Predictions:")
        for i in range(min(10, len(y_test))):
            actual = y_test.iloc[i]
            predicted = y_pred[i]
            error = abs(actual - predicted)
            logger.info(f"      Actual: ₹{actual:,.0f} | Predicted: ₹{predicted:,.0f} | Error: ₹{error:,.0f}")
        
        # Save model
        joblib.dump(model, self.models_dir / 'salary_model_jobs.pkl')
        joblib.dump(scaler, self.models_dir / 'salary_scaler_jobs.pkl')
        
        logger.info("\n   ✅ Salary model saved!")
        
        return model, scaler, r2
    
    def train_all(self):
        """Train all models"""
        logger.info("\n" + "="*70)
        logger.info("🚀 JOB-BASED MODEL TRAINING")
        logger.info("="*70)
        
        # Load data
        df = self.load_training_data()
        if df is None:
            return
        
        # Engineer features
        features = self.engineer_features(df)
        
        # Train models
        career_model, career_scaler, career_encoder, career_acc = self.train_career_model(df, features)
        salary_model, salary_scaler, salary_r2 = self.train_salary_model(df, features)
        
        # Summary
        logger.info("\n" + "="*70)
        logger.info("📊 TRAINING SUMMARY")
        logger.info("="*70)
        logger.info(f"   Training Data: {len(df):,} job postings")
        logger.info(f"   Career Model Accuracy: {career_acc:.4f}")
        logger.info(f"   Salary Model R²: {salary_r2:.4f}")
        logger.info(f"\n   Models saved to: {self.models_dir}")
        logger.info(f"   Files created:")
        logger.info(f"      - career_model_jobs.pkl")
        logger.info(f"      - career_scaler_jobs.pkl")
        logger.info(f"      - career_encoder_jobs.pkl")
        logger.info(f"      - salary_model_jobs.pkl")
        logger.info(f"      - salary_scaler_jobs.pkl")
        logger.info("="*70)


def main():
    """Main execution"""
    trainer = JobBasedModelTrainer()
    trainer.train_all()


if __name__ == "__main__":
    main()
