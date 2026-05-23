"""
Incremental Model Training Module
Handles retraining of ML models with new live data
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import logging
import joblib
import os
from pathlib import Path
import json

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, r2_score, mean_absolute_error

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.bigquery_data_provider import get_data_provider
from utils.mongodb_client import MongoDBClient
from utils.logger import setup_logger

logger = setup_logger('incremental_training')

class ModelStore:
    """Handles model storage and versioning (with MongoDB GridFS fallback for serverless)"""
    
    def __init__(self, models_dir: str = None):
        if models_dir is None:
            # Check if running in Vercel or cloud environment
            if os.getenv("VERCEL") or os.getenv("ENVIRONMENT") == "cloud":
                self.models_dir = Path("/tmp/models")
            else:
                self.models_dir = Path("models")
        else:
            self.models_dir = Path(models_dir)
            
        self.models_dir.mkdir(exist_ok=True, parents=True)
        
        # Model file paths
        self.career_model_rf_path = self.models_dir / "career_model_rf.pkl"
        self.career_model_gb_path = self.models_dir / "career_model_gb.pkl"
        self.career_scaler_path = self.models_dir / "career_scaler_advanced.pkl"
        self.career_encoder_path = self.models_dir / "career_encoder_advanced.pkl"
        
        self.salary_model_path = self.models_dir / "salary_model_advanced.pkl"
        self.salary_scaler_path = self.models_dir / "salary_scaler_advanced.pkl"
        
        # Metadata file
        self.metadata_path = self.models_dir / "model_metadata.json"

    def save_to_gridfs(self, filename: str, local_path: Path) -> bool:
        """Save a file to MongoDB GridFS"""
        try:
            mongo = MongoDBClient()
            if mongo.connect():
                import gridfs
                fs = gridfs.GridFS(mongo.db)
                
                # Read the file
                with open(local_path, 'rb') as f:
                    data = f.read()
                
                # Delete old version to save space
                try:
                    for grid_file in fs.find({"filename": filename}):
                        fs.delete(grid_file._id)
                except Exception as e:
                    logger.warning(f"Failed to delete old file {filename}: {e}")
                
                # Put new file
                fs.put(data, filename=filename)
                logger.info(f"Saved {filename} to GridFS successfully")
                mongo.close()
                return True
        except Exception as e:
            logger.error(f"Failed to save {filename} to GridFS: {e}")
        return False

    def load_from_gridfs(self, filename: str, local_path: Path) -> bool:
        """Load a file from MongoDB GridFS if it exists"""
        try:
            # Check if file exists locally and is valid
            if local_path.exists() and local_path.stat().st_size > 0:
                return True
                
            mongo = MongoDBClient()
            if mongo.connect():
                import gridfs
                fs = gridfs.GridFS(mongo.db)
                try:
                    grid_out = fs.get_last_version(filename=filename)
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(local_path, 'wb') as f:
                        f.write(grid_out.read())
                    logger.info(f"Loaded {filename} from GridFS successfully")
                    mongo.close()
                    return True
                except Exception as e:
                    logger.warning(f"Filename {filename} not found in GridFS: {e}")
                mongo.close()
        except Exception as e:
            logger.error(f"Failed to load {filename} from GridFS: {e}")
        return False
    
    def save_career_models(self, rf_model, gb_model, scaler, encoder, metadata: Dict):
        """Save career prediction models"""
        try:
            # Save locally
            joblib.dump(rf_model, self.career_model_rf_path)
            joblib.dump(gb_model, self.career_model_gb_path)
            joblib.dump(scaler, self.career_scaler_path)
            joblib.dump(encoder, self.career_encoder_path)
            
            # Save to GridFS
            self.save_to_gridfs("career_model_rf.pkl", self.career_model_rf_path)
            self.save_to_gridfs("career_model_gb.pkl", self.career_model_gb_path)
            self.save_to_gridfs("career_scaler_advanced.pkl", self.career_scaler_path)
            self.save_to_gridfs("career_encoder_advanced.pkl", self.career_encoder_path)
            
            # Update metadata
            self._update_metadata('career', metadata)
            
            logger.info("Career models saved successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to save career models: {e}")
            return False
    
    def save_salary_model(self, model, scaler, metadata: Dict):
        """Save salary prediction model"""
        try:
            # Save locally
            joblib.dump(model, self.salary_model_path)
            joblib.dump(scaler, self.salary_scaler_path)
            
            # Save to GridFS
            self.save_to_gridfs("salary_model_advanced.pkl", self.salary_model_path)
            self.save_to_gridfs("salary_scaler_advanced.pkl", self.salary_scaler_path)
            
            # Update metadata
            self._update_metadata('salary', metadata)
            
            logger.info("Salary model saved successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to save salary model: {e}")
            return False
    
    def load_career_models(self) -> Tuple[Optional[object], Optional[object], Optional[object], Optional[object]]:
        """Load career prediction models"""
        try:
            # Try to fetch from GridFS if not local
            self.load_from_gridfs("career_model_rf.pkl", self.career_model_rf_path)
            self.load_from_gridfs("career_model_gb.pkl", self.career_model_gb_path)
            self.load_from_gridfs("career_scaler_advanced.pkl", self.career_scaler_path)
            self.load_from_gridfs("career_encoder_advanced.pkl", self.career_encoder_path)
            
            if all(path.exists() for path in [self.career_model_rf_path, self.career_model_gb_path, 
                                             self.career_scaler_path, self.career_encoder_path]):
                rf_model = joblib.load(self.career_model_rf_path)
                gb_model = joblib.load(self.career_model_gb_path)
                scaler = joblib.load(self.career_scaler_path)
                encoder = joblib.load(self.career_encoder_path)
                return rf_model, gb_model, scaler, encoder
            return None, None, None, None
        except Exception as e:
            logger.error(f"Failed to load career models: {e}")
            return None, None, None, None
    
    def load_salary_model(self) -> Tuple[Optional[object], Optional[object]]:
        """Load salary prediction model"""
        try:
            # Try to fetch from GridFS if not local
            self.load_from_gridfs("salary_model_advanced.pkl", self.salary_model_path)
            self.load_from_gridfs("salary_scaler_advanced.pkl", self.salary_scaler_path)
            
            if self.salary_model_path.exists() and self.salary_scaler_path.exists():
                model = joblib.load(self.salary_model_path)
                scaler = joblib.load(self.salary_scaler_path)
                return model, scaler
            return None, None
        except Exception as e:
            logger.error(f"Failed to load salary model: {e}")
            return None, None
    
    def _update_metadata(self, model_type: str, metadata: Dict):
        """Update model metadata"""
        try:
            # Fetch existing metadata from GridFS
            self.load_from_gridfs("model_metadata.json", self.metadata_path)
            
            # Load existing metadata
            if self.metadata_path.exists():
                with open(self.metadata_path, 'r') as f:
                    all_metadata = json.load(f)
            else:
                all_metadata = {}
            
            # Update metadata for this model type
            all_metadata[model_type] = {
                **metadata,
                'updated_at': datetime.now().isoformat(),
                'version': all_metadata.get(model_type, {}).get('version', 0) + 1
            }
            
            # Save updated metadata locally
            with open(self.metadata_path, 'w') as f:
                json.dump(all_metadata, f, indent=2)
                
            # Save to GridFS
            self.save_to_gridfs("model_metadata.json", self.metadata_path)
                
        except Exception as e:
            logger.error(f"Failed to update metadata: {e}")
    
    def get_model_metadata(self) -> Dict:
        """Get model metadata"""
        try:
            # Fetch metadata from GridFS
            self.load_from_gridfs("model_metadata.json", self.metadata_path)
            if self.metadata_path.exists():
                with open(self.metadata_path, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return {}

class DataValidator:
    """Validates data quality for model training"""
    
    def __init__(self):
        self.min_samples = 100
        self.min_features = 5
    
    def validate_training_data(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Validate training data quality"""
        validation_results = {
            'is_valid': True,
            'issues': [],
            'stats': {}
        }
        
        try:
            # Check sample size
            n_samples = len(X)
            validation_results['stats']['n_samples'] = n_samples
            
            if n_samples < self.min_samples:
                validation_results['is_valid'] = False
                validation_results['issues'].append(f"Insufficient samples: {n_samples} < {self.min_samples}")
            
            # Check feature count
            n_features = X.shape[1]
            validation_results['stats']['n_features'] = n_features
            
            if n_features < self.min_features:
                validation_results['is_valid'] = False
                validation_results['issues'].append(f"Insufficient features: {n_features} < {self.min_features}")
            
            # Check for missing values
            missing_ratio = X.isnull().sum().sum() / (X.shape[0] * X.shape[1])
            validation_results['stats']['missing_ratio'] = missing_ratio
            
            if missing_ratio > 0.3:
                validation_results['is_valid'] = False
                validation_results['issues'].append(f"Too many missing values: {missing_ratio:.2%}")
            
            # Check target distribution
            if hasattr(y, 'value_counts'):
                target_distribution = y.value_counts()
                validation_results['stats']['target_distribution'] = {str(k): int(v) for k, v in target_distribution.to_dict().items()}
                
                # Check for class imbalance (for classification)
                min_class_ratio = target_distribution.min() / target_distribution.sum()
                if min_class_ratio < 0.01:  # Less than 1%
                    validation_results['issues'].append(f"Severe class imbalance: min class ratio {min_class_ratio:.2%}")
            
            logger.info(f"Data validation completed: {validation_results}")
            return validation_results
            
        except Exception as e:
            logger.error(f"Data validation failed: {e}")
            return {
                'is_valid': False,
                'issues': [f"Validation error: {e}"],
                'stats': {}
            }

class IncrementalModelTrainer:
    """Main class for incremental model training"""
    
    def __init__(self):
        self.model_store = ModelStore()
        self.data_validator = DataValidator()
        self.data_provider = get_data_provider()
        self.mongodb_client = MongoDBClient()
        
        # Training parameters
        self.retrain_threshold_samples = 500  # Minimum new samples to trigger retraining
        self.retrain_threshold_days = 7       # Maximum days between retraining
        self.test_size = 0.2
        self.random_state = 42
        
        logger.info("Incremental Model Trainer initialized")
    
    def should_retrain(self) -> bool:
        """Determine if models should be retrained"""
        try:
            # Get model metadata
            metadata = self.model_store.get_model_metadata()
            
            # Check if models exist
            if not metadata:
                logger.info("No existing models found, retraining needed")
                return True
            
            # Check age of models
            career_metadata = metadata.get('career', {})
            salary_metadata = metadata.get('salary', {})
            
            # Get the most recent model update
            last_update = None
            for model_meta in [career_metadata, salary_metadata]:
                if 'updated_at' in model_meta:
                    model_update = datetime.fromisoformat(model_meta['updated_at'])
                    if last_update is None or model_update > last_update:
                        last_update = model_update
            
            if last_update:
                days_since_update = (datetime.now() - last_update).days
                if days_since_update >= self.retrain_threshold_days:
                    logger.info(f"Models are {days_since_update} days old, retraining needed")
                    return True
            
            # Check for new data volume
            new_samples = self._count_new_samples_since_last_training(last_update)
            if new_samples >= self.retrain_threshold_samples:
                logger.info(f"Found {new_samples} new samples, retraining needed")
                return True
            
            logger.info(f"Retraining not needed: {new_samples} new samples, {days_since_update if last_update else 'N/A'} days old")
            return False
            
        except Exception as e:
            logger.error(f"Error checking retrain condition: {e}")
            return True  # Default to retraining on error
    
    def _count_new_samples_since_last_training(self, last_update: Optional[datetime]) -> int:
        """Count new samples since last training"""
        try:
            if not last_update:
                # If no last update, count all recent samples
                last_update = datetime.now() - timedelta(days=30)
            
            # Count new jobs in MongoDB
            jobs_collection = self.mongodb_client.get_collection('live_jobs')
            new_jobs = jobs_collection.count_documents({
                'ingested_at': {'$gte': last_update}
            })
            
            return new_jobs
            
        except Exception as e:
            logger.error(f"Error counting new samples: {e}")
            return 0
    
    def train_incremental(self) -> Dict[str, Any]:
        """Perform incremental training of all models"""
        training_results = {
            'career_model': {},
            'salary_model': {},
            'timestamp': datetime.now().isoformat(),
            'success': False
        }
        
        try:
            logger.info("Starting incremental model training")
            
            # Load fresh data from BigQuery
            training_data = self._load_training_data()
            
            if training_data is None or training_data.empty:
                raise Exception("Failed to load training data")
            
            # Train career prediction model
            logger.info("Training career prediction model")
            career_results = self._train_career_model(training_data)
            training_results['career_model'] = career_results
            
            # Train salary prediction model
            logger.info("Training salary prediction model")
            salary_results = self._train_salary_model(training_data)
            training_results['salary_model'] = salary_results
            
            training_results['success'] = True
            logger.info("Incremental training completed successfully")
            
            return training_results
            
        except Exception as e:
            error_msg = f"Incremental training failed: {e}"
            logger.error(error_msg)
            training_results['error'] = error_msg
            return training_results
    
    def _load_training_data(self) -> Optional[pd.DataFrame]:
        """Load training data from BigQuery and MongoDB"""
        try:
            # Load data from BigQuery (processed data)
            bq_data = self.data_provider.get_training_data()
            
            # Load recent live data from MongoDB
            live_data = self._load_live_data_for_training()
            
            # Combine datasets
            if bq_data is not None and not bq_data.empty:
                if live_data is not None and not live_data.empty:
                    combined_data = pd.concat([bq_data, live_data], ignore_index=True)
                else:
                    combined_data = bq_data
            elif live_data is not None and not live_data.empty:
                combined_data = live_data
            else:
                logger.error("No training data available")
                return None
            
            # Remove duplicates using hashable columns to avoid unhashable list types (skills column)
            if not combined_data.empty:
                subset_cols = [col for col in ['title', 'company', 'location'] if col in combined_data.columns]
                combined_data = combined_data.drop_duplicates(subset=subset_cols) if subset_cols else combined_data.drop_duplicates()
            
            logger.info(f"Loaded {len(combined_data)} training samples")
            return combined_data
            
        except Exception as e:
            logger.error(f"Error loading training data: {e}")
            return None
    
    def _load_live_data_for_training(self) -> Optional[pd.DataFrame]:
        """Load and process live data from MongoDB for training"""
        try:
            # Get live jobs
            jobs_collection = self.mongodb_client.get_collection('live_jobs')
            
            # Get recent jobs (last 30 days)
            cutoff_date = datetime.now() - timedelta(days=30)
            jobs_cursor = jobs_collection.find({
                'ingested_at': {'$gte': cutoff_date},
                'is_active': True
            })
            
            jobs_data = []
            for job in jobs_cursor:
                # Extract features for training
                job_features = self._extract_features_from_job(job)
                if job_features:
                    jobs_data.append(job_features)
            
            if not jobs_data:
                logger.info("No live data available for training")
                return None
            
            df = pd.DataFrame(jobs_data)
            logger.info(f"Processed {len(df)} live jobs for training")
            return df
            
        except Exception as e:
            logger.error(f"Error loading live data: {e}")
            return None
    
    def _extract_features_from_job(self, job: Dict) -> Optional[Dict]:
        """Extract training features from a job document"""
        try:
            # This is a simplified feature extraction
            # In production, you'd want more sophisticated feature engineering
            
            sal_min = job.get('salary_min')
            sal_max = job.get('salary_max')
            sal_min = sal_min if sal_min is not None else 0
            sal_max = sal_max if sal_max is not None else 0
            
            features = {
                'title': job.get('title', ''),
                'company': job.get('company', ''),
                'location': job.get('location', ''),
                'skills': job.get('skills', []),
                'experience_required': job.get('experience_required', ''),
                'salary_min': sal_min,
                'salary_max': sal_max,
                'job_type': job.get('job_type', 'full_time'),
                'description_length': len(job.get('description', '')),
                'skills_count': len(job.get('skills', [])),
                'has_salary': 1 if sal_min > 0 else 0,
                'source': job.get('source', 'unknown')
            }
            
            # Infer career from title (simplified)
            title_lower = features['title'].lower()
            if 'data scientist' in title_lower or 'data analyst' in title_lower:
                features['career'] = 'Data Scientist'
            elif 'software engineer' in title_lower or 'developer' in title_lower:
                features['career'] = 'Software Engineer'
            elif 'product manager' in title_lower:
                features['career'] = 'Product Manager'
            else:
                features['career'] = 'Software Engineer'  # Default
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting features from job: {e}")
            return None
    
    def _train_career_model(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Train career prediction model"""
        try:
            # Prepare features and target
            X, y = self._prepare_career_training_data(data)
            
            # Validate data
            validation = self.data_validator.validate_training_data(X, y)
            if not validation['is_valid']:
                raise Exception(f"Data validation failed: {validation['issues']}")
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.test_size, random_state=self.random_state, stratify=y
            )
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Encode target
            encoder = LabelEncoder()
            y_train_encoded = encoder.fit_transform(y_train)
            y_test_encoded = encoder.transform(y_test)
            
            # Train ensemble models
            rf_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=self.random_state,
                n_jobs=-1
            )
            
            gb_model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=6,
                random_state=self.random_state
            )
            
            # Fit models
            rf_model.fit(X_train_scaled, y_train_encoded)
            gb_model.fit(X_train_scaled, y_train_encoded)
            
            # Evaluate models
            rf_pred = rf_model.predict(X_test_scaled)
            gb_pred = gb_model.predict(X_test_scaled)
            
            # Ensemble prediction (average probabilities)
            rf_proba = rf_model.predict_proba(X_test_scaled)
            gb_proba = gb_model.predict_proba(X_test_scaled)
            ensemble_proba = (rf_proba + gb_proba) / 2
            ensemble_pred = np.argmax(ensemble_proba, axis=1)
            
            # Calculate metrics
            rf_accuracy = accuracy_score(y_test_encoded, rf_pred)
            gb_accuracy = accuracy_score(y_test_encoded, gb_pred)
            ensemble_accuracy = accuracy_score(y_test_encoded, ensemble_pred)
            
            # Save models
            metadata = {
                'rf_accuracy': rf_accuracy,
                'gb_accuracy': gb_accuracy,
                'ensemble_accuracy': ensemble_accuracy,
                'n_samples': len(X),
                'n_features': X.shape[1],
                'classes': encoder.classes_.tolist(),
                'feature_names': X.columns.tolist()
            }
            
            success = self.model_store.save_career_models(rf_model, gb_model, scaler, encoder, metadata)
            
            results = {
                'success': success,
                'rf_accuracy': rf_accuracy,
                'gb_accuracy': gb_accuracy,
                'ensemble_accuracy': ensemble_accuracy,
                'n_samples': len(X),
                'validation': validation
            }
            
            logger.info(f"Career model training completed: {ensemble_accuracy:.4f} accuracy")
            return results
            
        except Exception as e:
            logger.error(f"Career model training failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _train_salary_model(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Train salary prediction model"""
        try:
            # Prepare features and target
            X, y = self._prepare_salary_training_data(data)
            
            # Validate data
            validation = self.data_validator.validate_training_data(X, pd.Series(y))
            if not validation['is_valid']:
                raise Exception(f"Data validation failed: {validation['issues']}")
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.test_size, random_state=self.random_state
            )
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train model
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=self.random_state,
                n_jobs=-1
            )
            
            model.fit(X_train_scaled, y_train)
            
            # Evaluate model
            y_pred = model.predict(X_test_scaled)
            r2 = r2_score(y_test, y_pred)
            mae = mean_absolute_error(y_test, y_pred)
            
            # Save model
            metadata = {
                'r2_score': r2,
                'mae': mae,
                'n_samples': len(X),
                'n_features': X.shape[1],
                'feature_names': X.columns.tolist()
            }
            
            success = self.model_store.save_salary_model(model, scaler, metadata)
            
            results = {
                'success': success,
                'r2_score': r2,
                'mae': mae,
                'n_samples': len(X),
                'validation': validation
            }
            
            logger.info(f"Salary model training completed: {r2:.4f} R² score")
            return results
            
        except Exception as e:
            logger.error(f"Salary model training failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _prepare_career_training_data(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare data for career model training"""
        # This is a simplified implementation
        # In production, you'd want more sophisticated feature engineering
        
        # Select relevant columns
        feature_columns = ['skills_count', 'description_length', 'has_salary']
        
        # Create dummy features for categorical variables
        if 'location' in data.columns:
            location_dummies = pd.get_dummies(data['location'], prefix='location')
            data = pd.concat([data, location_dummies], axis=1)
            feature_columns.extend(location_dummies.columns.tolist())
        
        if 'job_type' in data.columns:
            job_type_dummies = pd.get_dummies(data['job_type'], prefix='job_type')
            data = pd.concat([data, job_type_dummies], axis=1)
            feature_columns.extend(job_type_dummies.columns.tolist())
        
        # Select features and target
        X = data[feature_columns].fillna(0)
        y = data['career']
        
        return X, y
    
    def _prepare_salary_training_data(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray]:
        """Prepare data for salary model training"""
        # Filter data with valid salaries
        salary_data = data[
            (data['salary_min'] > 0) & 
            (data['salary_max'] > 0) & 
            (data['salary_min'] <= data['salary_max'])
        ].copy()
        
        # Use average salary as target
        salary_data['avg_salary'] = (salary_data['salary_min'] + salary_data['salary_max']) / 2
        
        # Select features
        feature_columns = ['skills_count', 'description_length']
        
        # Add categorical features
        if 'location' in salary_data.columns:
            location_dummies = pd.get_dummies(salary_data['location'], prefix='location')
            salary_data = pd.concat([salary_data, location_dummies], axis=1)
            feature_columns.extend(location_dummies.columns.tolist())
        
        if 'career' in salary_data.columns:
            career_dummies = pd.get_dummies(salary_data['career'], prefix='career')
            salary_data = pd.concat([salary_data, career_dummies], axis=1)
            feature_columns.extend(career_dummies.columns.tolist())
        
        X = salary_data[feature_columns].fillna(0)
        y = salary_data['avg_salary'].values
        
        return X, y

def main():
    """Main function for testing incremental training"""
    logging.basicConfig(level=logging.INFO)
    
    trainer = IncrementalModelTrainer()
    
    # Check if retraining is needed
    should_retrain = trainer.should_retrain()
    print(f"Should retrain: {should_retrain}")
    
    if should_retrain:
        # Run incremental training
        results = trainer.train_incremental()
        print("Training Results:")
        print(json.dumps(results, indent=2, default=str))
    else:
        print("Retraining not needed")

if __name__ == "__main__":
    main()