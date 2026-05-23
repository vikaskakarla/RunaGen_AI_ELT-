"""
Live Pipeline Scheduler
Orchestrates the entire live data pipeline with proper scheduling
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from src.etl.live_data_ingestion import LiveDataIngestion
from src.etl.mongodb_to_bigquery import MongoDBToBigQueryETL
from src.ml.incremental_training import IncrementalModelTrainer
from src.utils.mongodb_client import MongoDBClient
from src.utils.logger import setup_logger

logger = setup_logger('live_pipeline_scheduler')

class LivePipelineScheduler:
    """
    Main scheduler for the live data pipeline
    Coordinates data ingestion, ETL, and model training
    """
    
    def __init__(self, mode: str = 'production'):
        self.mode = mode
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        
        # Initialize components
        self.data_ingestion = LiveDataIngestion()
        self.etl_pipeline = MongoDBToBigQueryETL()
        self.model_trainer = IncrementalModelTrainer()
        self.mongodb_client = MongoDBClient()
        
        # Pipeline state tracking
        self.pipeline_state = {
            'last_data_fetch': None,
            'last_etl_run': None,
            'last_model_training': None,
            'current_jobs': [],
            'errors': [],
            'stats': {}
        }
        
        # Setup event listeners
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
        
        logger.info(f"Live Pipeline Scheduler initialized in {mode} mode")
    
    def setup_jobs(self):
        """Setup all scheduled jobs based on mode"""
        logger.info(f"Setting up scheduled jobs for {self.mode} mode")
        
        if self.mode == 'production':
            self._setup_production_schedule()
        elif self.mode == 'development':
            self._setup_development_schedule()
        elif self.mode == 'testing':
            self._setup_testing_schedule()
        else:
            raise ValueError(f"Unknown mode: {self.mode}")
    
    def _setup_production_schedule(self):
        """Production schedule - optimized for real-world usage"""
        
        # 1. Hourly data ingestion (fetch fresh jobs)
        self.scheduler.add_job(
            self.fetch_live_data,
            IntervalTrigger(hours=1),
            id='hourly_data_fetch',
            name='Hourly Live Data Fetch',
            max_instances=1,
            coalesce=True,
            kwargs={'limit': 200}
        )
        
        # 2. Every 4 hours - ETL pipeline (process new data)
        self.scheduler.add_job(
            self.run_etl_pipeline,
            IntervalTrigger(hours=4),
            id='etl_processing',
            name='ETL Pipeline Processing',
            max_instances=1,
            coalesce=True
        )
        
        # 3. Daily at 2 AM - Full model retraining
        self.scheduler.add_job(
            self.retrain_models,
            CronTrigger(hour=2, minute=0),
            id='daily_model_training',
            name='Daily Model Retraining',
            max_instances=1,
            coalesce=True
        )
        
        # 4. Every 6 hours - Dashboard data refresh
        self.scheduler.add_job(
            self.refresh_dashboard_data,
            IntervalTrigger(hours=6),
            id='dashboard_refresh',
            name='Dashboard Data Refresh',
            max_instances=1,
            coalesce=True
        )
        
        # 5. Every 30 minutes - Health check and cleanup
        self.scheduler.add_job(
            self.health_check_and_cleanup,
            IntervalTrigger(minutes=30),
            id='health_check',
            name='Health Check and Cleanup',
            max_instances=1,
            coalesce=True
        )
        
        logger.info("Production schedule configured")
    
    def _setup_development_schedule(self):
        """Development schedule - more frequent for testing"""
        
        # Every 2 hours - data fetch
        self.scheduler.add_job(
            self.fetch_live_data,
            IntervalTrigger(hours=2),
            id='dev_data_fetch',
            kwargs={'limit': 100}
        )
        
        # Every 6 hours - ETL
        self.scheduler.add_job(
            self.run_etl_pipeline,
            IntervalTrigger(hours=6),
            id='dev_etl_processing'
        )
        
        # Daily at 3 AM - model training
        self.scheduler.add_job(
            self.retrain_models,
            CronTrigger(hour=3, minute=0),
            id='dev_model_training'
        )
        
        logger.info("Development schedule configured")
    
    def _setup_testing_schedule(self):
        """Testing schedule - very frequent for rapid iteration"""
        
        # Every 30 minutes - data fetch (small batches)
        self.scheduler.add_job(
            self.fetch_live_data,
            IntervalTrigger(minutes=30),
            id='test_data_fetch',
            kwargs={'limit': 50}
        )
        
        # Every 2 hours - ETL
        self.scheduler.add_job(
            self.run_etl_pipeline,
            IntervalTrigger(hours=2),
            id='test_etl_processing'
        )
        
        # Every 4 hours - model training
        self.scheduler.add_job(
            self.retrain_models,
            IntervalTrigger(hours=4),
            id='test_model_training'
        )
        
        logger.info("Testing schedule configured")
    
    async def fetch_live_data(self, limit: int = 200):
        """Fetch live data from APIs"""
        if self.is_running:
            logger.warning("Pipeline already running, skipping data fetch")
            return
        
        try:
            self.is_running = True
            logger.info(f"Starting live data fetch (limit: {limit})")
            
            # Fetch data from all sources
            results = self.data_ingestion.fetch_all_live_data(total_limit=limit)
            
            # Update pipeline state
            self.pipeline_state['last_data_fetch'] = datetime.now().isoformat()
            self.pipeline_state['stats']['last_fetch_results'] = results
            
            # Log results
            jobs_fetched = results.get('jobs_fetched', 0)
            skills_updated = results.get('skills_updated', 0)
            
            logger.info(f"Live data fetch completed: {jobs_fetched} jobs, {skills_updated} skills")
            
            # Store pipeline state
            await self._save_pipeline_state()
            
            return results
            
        except Exception as e:
            error_msg = f"Live data fetch failed: {e}"
            logger.error(error_msg)
            self.pipeline_state['errors'].append({
                'timestamp': datetime.now().isoformat(),
                'stage': 'data_fetch',
                'error': error_msg
            })
            raise
        finally:
            self.is_running = False
    
    async def run_etl_pipeline(self):
        """Run the ETL pipeline to process new data"""
        if self.is_running:
            logger.warning("Pipeline already running, skipping ETL")
            return
        
        try:
            self.is_running = True
            logger.info("Starting ETL pipeline processing")
            
            # Check if we have new data to process
            stats = self.data_ingestion.get_ingestion_stats()
            recent_jobs = stats.get('recent_jobs_24h', 0)
            
            if recent_jobs == 0:
                logger.info("No new data to process, skipping ETL")
                return
            
            # Run ETL stages
            etl_results = {}
            
            # 1. Extract live jobs from MongoDB and load to BigQuery Bronze
            logger.info("Extracting live jobs to BigQuery Bronze layer")
            jobs_df = self.etl_pipeline.extract_live_jobs_from_mongodb()
            if not jobs_df.empty:
                self.etl_pipeline.load_to_bigquery(jobs_df, 'raw_jobs_live', self.etl_pipeline.dataset_bronze)
                etl_results['bronze_jobs'] = len(jobs_df)
            
            # 2. Extract live skills
            logger.info("Extracting live skills to BigQuery Bronze layer")
            skills_df = self.etl_pipeline.extract_live_skills_from_mongodb()
            if not skills_df.empty:
                self.etl_pipeline.load_to_bigquery(skills_df, 'raw_skills_live', self.etl_pipeline.dataset_bronze)
                etl_results['bronze_skills'] = len(skills_df)
            
            # 3. Run dbt transformations
            logger.info("Running dbt transformations")
            await self._run_dbt_transformations()
            
            # 4. Data quality validation
            logger.info("Running data quality validation")
            validation_results = await self._validate_data_quality()
            etl_results['validation'] = validation_results
            
            # Update pipeline state
            self.pipeline_state['last_etl_run'] = datetime.now().isoformat()
            self.pipeline_state['stats']['last_etl_results'] = etl_results
            
            logger.info(f"ETL pipeline completed: {etl_results}")
            
            # Store pipeline state
            await self._save_pipeline_state()
            
            return etl_results
            
        except Exception as e:
            error_msg = f"ETL pipeline failed: {e}"
            logger.error(error_msg)
            self.pipeline_state['errors'].append({
                'timestamp': datetime.now().isoformat(),
                'stage': 'etl_pipeline',
                'error': error_msg
            })
            raise
        finally:
            self.is_running = False
    
    async def retrain_models(self):
        """Retrain ML models with new data"""
        if self.is_running:
            logger.warning("Pipeline already running, skipping model training")
            return
        
        try:
            self.is_running = True
            logger.info("Starting model retraining")
            
            # Check if retraining is needed
            should_retrain = self.model_trainer.should_retrain()
            if not should_retrain:
                logger.info("Model retraining not needed, skipping")
                return
            
            # Run incremental training
            training_results = self.model_trainer.train_incremental()
            
            # Update pipeline state
            self.pipeline_state['last_model_training'] = datetime.now().isoformat()
            self.pipeline_state['stats']['last_training_results'] = training_results
            
            logger.info(f"Model retraining completed: {training_results}")
            
            # Store pipeline state
            await self._save_pipeline_state()
            
            return training_results
            
        except Exception as e:
            error_msg = f"Model retraining failed: {e}"
            logger.error(error_msg)
            self.pipeline_state['errors'].append({
                'timestamp': datetime.now().isoformat(),
                'stage': 'model_training',
                'error': error_msg
            })
            raise
        finally:
            self.is_running = False
    
    async def refresh_dashboard_data(self):
        """Refresh dashboard data and cache"""
        try:
            logger.info("Refreshing dashboard data")
            
            # Get latest statistics
            ingestion_stats = self.data_ingestion.get_ingestion_stats()
            
            # Update dashboard cache in MongoDB
            dashboard_data = {
                'timestamp': datetime.now().isoformat(),
                'ingestion_stats': ingestion_stats,
                'pipeline_state': self.pipeline_state,
                'live_mode': True
            }
            
            # Store in MongoDB for dashboard consumption
            collection = self.mongodb_client.get_collection('dashboard_cache')
            collection.update_one(
                {'type': 'live_dashboard_data'},
                {'$set': dashboard_data},
                upsert=True
            )
            
            logger.info("Dashboard data refreshed")
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Dashboard refresh failed: {e}")
            raise
    
    async def health_check_and_cleanup(self):
        """Perform health checks and cleanup old data"""
        try:
            logger.info("Running health check and cleanup")
            
            # Health checks
            health_status = {
                'mongodb_connected': self.mongodb_client.is_connected(),
                'scheduler_running': self.scheduler.running,
                'last_data_fetch_age': self._get_time_since_last_fetch(),
                'error_count_24h': len([e for e in self.pipeline_state['errors'] 
                                      if self._is_recent_error(e, hours=24)])
            }
            
            # Cleanup old data (keep last 30 days)
            cleanup_date = datetime.now() - timedelta(days=30)
            
            # Cleanup old jobs
            jobs_collection = self.mongodb_client.get_collection('live_jobs')
            deleted_jobs = jobs_collection.delete_many({
                'ingested_at': {'$lt': cleanup_date}
            }).deleted_count
            
            # Cleanup old errors (keep last 7 days)
            error_cutoff = datetime.now() - timedelta(days=7)
            self.pipeline_state['errors'] = [
                e for e in self.pipeline_state['errors']
                if datetime.fromisoformat(e['timestamp']) > error_cutoff
            ]
            
            logger.info(f"Health check completed. Cleaned up {deleted_jobs} old jobs")
            
            # Store health status
            health_collection = self.mongodb_client.get_collection('pipeline_health')
            health_collection.insert_one({
                'timestamp': datetime.now().isoformat(),
                'health_status': health_status,
                'cleanup_stats': {'deleted_jobs': deleted_jobs}
            })
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise
    
    async def _run_dbt_transformations(self):
        """Run dbt transformations"""
        import subprocess
        
        try:
            # Change to dbt directory
            dbt_dir = Path(__file__).parent.parent.parent / 'dbt_transforms'
            
            # Run silver layer transformations
            result = subprocess.run(
                ['dbt', 'run', '--models', 'silver.*'],
                cwd=dbt_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                raise Exception(f"dbt silver run failed: {result.stderr}")
            
            # Run gold layer transformations
            result = subprocess.run(
                ['dbt', 'run', '--models', 'gold.*'],
                cwd=dbt_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                raise Exception(f"dbt gold run failed: {result.stderr}")
            
            logger.info("dbt transformations completed successfully")
            
        except subprocess.TimeoutExpired:
            raise Exception("dbt transformations timed out")
        except Exception as e:
            raise Exception(f"dbt transformations failed: {e}")
    
    async def _validate_data_quality(self) -> Dict[str, Any]:
        """Validate data quality after ETL"""
        try:
            # Get MongoDB stats
            mongo_stats = self.data_ingestion.get_ingestion_stats()
            
            # Get BigQuery stats (simplified)
            bq_stats = self.etl_pipeline.get_bigquery_stats()
            
            # Basic validation checks
            validation_results = {
                'mongodb_jobs': mongo_stats.get('total_jobs', 0),
                'bigquery_jobs': bq_stats.get('raw_jobs', 0),
                'data_freshness_hours': self._get_time_since_last_fetch(),
                'validation_passed': True,
                'issues': []
            }
            
            # Check for data freshness
            if validation_results['data_freshness_hours'] > 2:
                validation_results['issues'].append('Data is more than 2 hours old')
            
            # Check for data volume
            if validation_results['mongodb_jobs'] == 0:
                validation_results['issues'].append('No jobs in MongoDB')
                validation_results['validation_passed'] = False
            
            return validation_results
            
        except Exception as e:
            return {
                'validation_passed': False,
                'error': str(e)
            }
    
    async def _save_pipeline_state(self):
        """Save pipeline state to MongoDB"""
        try:
            collection = self.mongodb_client.get_collection('pipeline_state')
            collection.update_one(
                {'type': 'live_pipeline_state'},
                {'$set': {
                    'state': self.pipeline_state,
                    'updated_at': datetime.now().isoformat()
                }},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to save pipeline state: {e}")
    
    def _get_time_since_last_fetch(self) -> float:
        """Get hours since last data fetch"""
        if not self.pipeline_state['last_data_fetch']:
            return float('inf')
        
        last_fetch = datetime.fromisoformat(self.pipeline_state['last_data_fetch'])
        return (datetime.now() - last_fetch).total_seconds() / 3600
    
    def _is_recent_error(self, error: Dict, hours: int = 24) -> bool:
        """Check if error is within specified hours"""
        try:
            error_time = datetime.fromisoformat(error['timestamp'])
            cutoff = datetime.now() - timedelta(hours=hours)
            return error_time > cutoff
        except:
            return False
    
    def _job_executed(self, event):
        """Handle job execution events"""
        logger.info(f"Job {event.job_id} executed successfully")
    
    def _job_error(self, event):
        """Handle job error events"""
        logger.error(f"Job {event.job_id} failed: {event.exception}")
        self.pipeline_state['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'job_id': event.job_id,
            'error': str(event.exception)
        })
    
    def start(self):
        """Start the scheduler"""
        logger.info("Starting Live Pipeline Scheduler")
        
        # Setup jobs
        self.setup_jobs()
        
        # Start scheduler
        self.scheduler.start()
        
        # Run initial data fetch
        asyncio.create_task(self.fetch_live_data(limit=100))
        
        logger.info("Live Pipeline Scheduler started successfully")
    
    def stop(self):
        """Stop the scheduler"""
        logger.info("Stopping Live Pipeline Scheduler")
        self.scheduler.shutdown()
        logger.info("Live Pipeline Scheduler stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        return {
            'mode': self.mode,
            'running': self.scheduler.running,
            'pipeline_state': self.pipeline_state,
            'scheduled_jobs': [
                {
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in self.scheduler.get_jobs()
            ]
        }

async def main():
    """Main function for running the scheduler"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Live Pipeline Scheduler')
    parser.add_argument('--mode', choices=['production', 'development', 'testing'], 
                       default='development', help='Scheduler mode')
    parser.add_argument('--run-once', action='store_true', 
                       help='Run pipeline once and exit')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create scheduler
    scheduler = LivePipelineScheduler(mode=args.mode)
    
    if args.run_once:
        # Run pipeline once
        logger.info("Running pipeline once")
        await scheduler.fetch_live_data()
        await scheduler.run_etl_pipeline()
        await scheduler.retrain_models()
        logger.info("Pipeline run completed")
    else:
        # Start continuous scheduling
        try:
            scheduler.start()
            
            # Keep running
            while True:
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())