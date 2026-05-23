"""
Improved Model Training with Better Preprocessing
Handles missing data, reduces overfitting, and improves generalization
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
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, classification_report, mean_absolute_error, r2_score
from sklearn.impute import SimpleImputer
import joblib
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImprovedModelTrainer:
    """Train models with better preprocessing and regularization"""
    
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
    
    def load_training_data(self):
        """Load and preprocess training data from BigQuery - CORRECT SCHEMA"""
        logger.info("📊 Loading training data from BigQuery...")
        
        # NOTE: raw_resumes has schema: resume_id, user_id, raw_text, file_name, 
        # file_size, uploaded_at, processing_status
        # This is RAW data - we need to process it first or use a different table
        # For now, we'll check if there's a processed resumes table
        
        query = f"""
        SELECT 
            raw_text,
            user_id,
            file_name,
            uploaded_at
        FROM `{self.project_id}.runagen_bronze.raw_resumes`
        WHERE raw_text IS NOT NULL 
            AND raw_text != ''
            AND CHAR_LENGTH(raw_text) > 100
        ORDER BY uploaded_at DESC
        LIMIT 10000
        """
        
        try:
            df = self.bq_client.query(query).to_dataframe()
            
            if df.empty:
                logger.error("❌ No training data found in BigQuery!")
                logger.info("ℹ️  raw_resumes table contains RAW resume text only")
                logger.info("ℹ️  You need to process resumes first to extract:")
                logger.info("     - skills")
                logger.info("     - experience_years")
                logger.info("     - education")
                logger.info("     - predicted_role")
                logger.info("     - predicted_salary")
                logger.info("\n💡 Solution: Create a 'processed_resumes' table with extracted features")
                return None
            
            logger.info(f"✅ Loaded {len(df)} resume records")
            logger.info("⚠️  WARNING: raw_resumes only has raw text - need feature extraction!")
            
            # For now, we can't train without processed features
            # We need skills, experience, education, etc.
            logger.error("❌ Cannot train models without processed resume features")
            logger.info("\n📋 Next Steps:")
            logger.info("   1. Create resume parser to extract features from raw_text")
            logger.info("   2. Store processed features in 'processed_resumes' table")
            logger.info("   3. Then run model training")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error loading training data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _fill_missing_salaries(self, df):
        """Fill missing salaries using role-based median"""
        logger.info("   Filling missing salaries...")
        
        # Calculate median salary per role
        role_medians = df.groupby('predicted_role')['predicted_salary'].median()
        
        # Fill missing values
        for role in df['predicted_role'].unique():
            mask = (df['predicted_role'] == role) & ((df['predicted_salary'].isna()) | (df['predicted_salary'] == 0))
            if mask.sum() > 0:
                median_sal = role_medians.get(role, 800000)  # Default 8L
                df.loc[mask, 'predicted_salary'] = median_sal
                logger.info(f"      Filled {mask.sum()} missing salaries for {role} with ₹{median_sal:,.0f}")
        
        return df
    
    def _remove_salary_outliers(self, df):
        """Remove salary outliers using IQR method"""
        logger.info("   Removing salary outliers...")
        
        Q1 = df['predicted_salary'].quantile(0.25)
        Q3 = df['predicted_salary'].quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - 3 * IQR
        upper_bound = Q3 + 3 * IQR
        
        before = len(df)
        df = df[(df['predicted_salary'] >= lower_bound) & (df['predicted_salary'] <= upper_bound)]
        after = len(df)
        
        logger.info(f"      Removed {before - after} salary outliers")
        
        return df
    
    def engineer_features(self, df):
        """Engineer features from resume data"""
        logger.info("🔧 Engineering features...")
        
        features = pd.DataFrame()
        
        # 1. Text-based features
        features['resume_length'] = df['resume_text'].str.len()
        features['word_count'] = df['resume_text'].str.split().str.len()
        
        # 2. Skills features
        features['skill_count'] = df['skills'].str.split(',').str.len()
        features['has_python'] = df['skills'].str.lower().str.contains('python').astype(int)
        features['has_sql'] = df['skills'].str.lower().str.contains('sql').astype(int)
        features['has_java'] = df['skills'].str.lower().str.contains('java').astype(int)
        features['has_javascript'] = df['skills'].str.lower().str.contains('javascript').astype(int)
        features['has_aws'] = df['skills'].str.lower().str.contains('aws').astype(int)
        features['has_docker'] = df['skills'].str.lower().str.contains('docker').astype(int)
        features['has_ml'] = df['skills'].str.lower().str.contains('machine learning|ml|tensorflow|pytorch').astype(int)
        
        # 3. Experience features
        features['experience_years'] = df['experience_years']
        features['experience_squared'] = df['experience_years'] ** 2  # Non-linear relationship
        features['is_fresher'] = (df['experience_years'] == 0).astype(int)
        features['is_senior'] = (df['experience_years'] >= 5).astype(int)
        
        # 4. Education features
        features['has_masters'] = df['education'].str.lower().str.contains('master|msc|mtech|mba').astype(int)
        features['has_phd'] = df['education'].str.lower().str.contains('phd|doctorate').astype(int)
        features['has_bachelors'] = df['education'].str.lower().str.contains('bachelor|btech|bsc|be ').astype(int)
        
        # 5. Resume quality features
        features['has_email'] = df['resume_text'].str.contains(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}').astype(int)
        features['has_phone'] = df['resume_text'].str.contains(r'\d{10}|\d{3}-\d{3}-\d{4}').astype(int)
        features['has_linkedin'] = df['resume_text'].str.lower().str.contains('linkedin').astype(int)
        features['has_github'] = df['resume_text'].str.lower().str.contains('github').astype(int)
        
        # Handle any remaining NaN values
        features = features.fillna(0)
        
        logger.info(f"✅ Engineered {len(features.columns)} features")
        
        return features
    
    def train_career_model(self, df, features):
        """Train career prediction model with cross-validation"""
        logger.info("\n🎯 Training Career Prediction Model...")
        logger.info("="*70)
        
        X = features
        y = df['predicted_role']
        
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
        
        # Train with regularization to prevent overfitting
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,  # Limit depth to prevent overfitting
            min_samples_split=10,  # Require more samples to split
            min_samples_leaf=5,  # Require more samples in leaf
            max_features='sqrt',  # Use subset of features
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
        joblib.dump(model, self.models_dir / 'career_model_improved.pkl')
        joblib.dump(scaler, self.models_dir / 'career_scaler_improved.pkl')
        joblib.dump(le, self.models_dir / 'career_encoder_improved.pkl')
        
        logger.info("\n   ✅ Career model saved!")
        
        return model, scaler, le, accuracy
    
    def train_salary_model(self, df, features):
        """Train salary prediction model with regularization"""
        logger.info("\n💰 Training Salary Prediction Model...")
        logger.info("="*70)
        
        X = features
        y = df['predicted_salary']
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train with regularization (Ridge regression to prevent overfitting)
        model = Ridge(alpha=10.0)  # L2 regularization
        
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
        for i in range(min(5, len(y_test))):
            logger.info(f"      Actual: ₹{y_test.iloc[i]:,.0f} | Predicted: ₹{y_pred[i]:,.0f}")
        
        # Save model
        joblib.dump(model, self.models_dir / 'salary_model_improved.pkl')
        joblib.dump(scaler, self.models_dir / 'salary_scaler_improved.pkl')
        
        logger.info("\n   ✅ Salary model saved!")
        
        return model, scaler, r2
    
    def train_all(self):
        """Train all models"""
        logger.info("\n" + "="*70)
        logger.info("🚀 IMPROVED MODEL TRAINING")
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
        logger.info(f"   Career Model Accuracy: {career_acc:.4f}")
        logger.info(f"   Salary Model R²: {salary_r2:.4f}")
        logger.info(f"\n   Models saved to: {self.models_dir}")
        logger.info("="*70)


def main():
    """Main execution"""
    trainer = ImprovedModelTrainer()
    trainer.train_all()


if __name__ == "__main__":
    main()
