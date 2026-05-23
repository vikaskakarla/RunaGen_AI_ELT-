"""
Startup Pipeline Runner
Automatically checks data freshness on server startup and runs the pipeline if stale.
Designed for users who only run the server a few minutes per day.

How it works:
1. On server startup, checks when data was last fetched (stored in MongoDB)
2. If data is older than DATA_STALENESS_HOURS (default 2h), triggers a background pipeline run
3. Pipeline stages run sequentially in a background task:
   a. Fetch fresh jobs from Adzuna API
   b. Run ELT (MongoDB → BigQuery Bronze)
   c. Retrain ML models (if enough new data or models are old)
4. The server is usable immediately — pipeline runs in background
5. Pipeline state is stored in MongoDB so next startup knows when data was last refreshed
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
import json
import sys
import os
import traceback

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger('startup_pipeline')


class StartupPipeline:
    """
    Runs the data pipeline on server startup if data is stale.
    
    This is the key component that makes the pipeline "live" even when
    you only run the server for a few minutes per day. Every time you
    start the server, it checks freshness and auto-refreshes.
    """
    
    def __init__(self, staleness_hours: float = 2.0):
        self.staleness_hours = staleness_hours
        self.is_running = False
        self._pipeline_status = {
            'state': 'idle',          # idle, checking, running, completed, failed
            'current_stage': None,     # data_fetch, etl, model_training
            'progress_pct': 0,
            'message': 'Waiting for startup check...',
            'last_run_result': None,
            'started_at': None,
            'completed_at': None,
            'error': None,
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current pipeline status (called by the /api/live/pipeline-status endpoint)"""
        return {**self._pipeline_status}
    
    def _update_status(self, state: str, stage: str = None, progress: int = 0, message: str = ''):
        """Update pipeline status for real-time frontend polling"""
        self._pipeline_status['state'] = state
        self._pipeline_status['current_stage'] = stage
        self._pipeline_status['progress_pct'] = progress
        self._pipeline_status['message'] = message
        logger.info(f"[Pipeline] {state.upper()}: {message}")
    
    async def check_and_run(self, mongodb_client=None):
        """
        Main entry point — called during server startup.
        Checks if data is stale and runs the pipeline in background if needed.
        """
        if self.is_running:
            logger.info("Pipeline already running, skipping startup check")
            return
        
        self._update_status('checking', message='Checking data freshness...')
        
        try:
            # Check data freshness from MongoDB
            hours_since_last_fetch = await self._get_hours_since_last_fetch(mongodb_client)
            
            if hours_since_last_fetch is None:
                self._update_status('running', 'data_fetch', 5,
                    'No previous data found — running first pipeline...')
                logger.info("No pipeline state found in MongoDB — running first pipeline")
            elif hours_since_last_fetch < self.staleness_hours:
                self._update_status('completed', message=
                    f'Data is fresh ({hours_since_last_fetch:.1f}h old, threshold: {self.staleness_hours}h). Skipping pipeline.')
                logger.info(f"Data is fresh ({hours_since_last_fetch:.1f}h old). Skipping pipeline.")
                return
            else:
                self._update_status('running', 'data_fetch', 5,
                    f'Data is {hours_since_last_fetch:.1f}h old (threshold: {self.staleness_hours}h). Refreshing...')
                logger.info(f"Data is stale ({hours_since_last_fetch:.1f}h). Starting pipeline...")
            
            # Run pipeline in background (non-blocking)
            asyncio.create_task(self._run_pipeline(mongodb_client))
            
        except Exception as e:
            error_msg = f"Startup pipeline check failed: {e}"
            self._update_status('failed', message=error_msg, progress=0)
            logger.error(error_msg)
            logger.error(traceback.format_exc())
    
    async def _get_hours_since_last_fetch(self, mongodb_client) -> Optional[float]:
        """Check MongoDB for when data was last fetched"""
        try:
            if not mongodb_client or mongodb_client.db is None:
                return None
            
            pipeline_state = mongodb_client.db['pipeline_state'].find_one(
                {'type': 'live_pipeline_state'}
            )
            
            if not pipeline_state or 'state' not in pipeline_state:
                return None
            
            last_fetch_str = pipeline_state['state'].get('last_data_fetch')
            if not last_fetch_str:
                return None
            
            last_fetch = datetime.fromisoformat(last_fetch_str)
            hours_ago = (datetime.now() - last_fetch).total_seconds() / 3600
            return hours_ago
            
        except Exception as e:
            logger.error(f"Error checking data freshness: {e}")
            return None
    
    async def _run_pipeline(self, mongodb_client):
        """Run the full pipeline (background task)"""
        self.is_running = True
        self._pipeline_status['started_at'] = datetime.now().isoformat()
        results = {'stages': {}}
        
        try:
            # ═══════════════════════════════════════════
            # STAGE 1: Fetch Live Data from Adzuna API
            # ═══════════════════════════════════════════
            self._update_status('running', 'data_fetch', 10,
                '📡 Stage 1/3: Fetching live job data from Adzuna API...')
            
            try:
                from src.etl.live_data_ingestion import LiveDataIngestion
                ingestion = LiveDataIngestion()
                limit = 50 if (os.getenv("VERCEL") or os.getenv("ENVIRONMENT") == "cloud") else 200
                fetch_results = ingestion.fetch_all_live_data(total_limit=limit)
                
                jobs_fetched = fetch_results.get('jobs_fetched', 0)
                skills_updated = fetch_results.get('skills_updated', 0)
                results['stages']['data_fetch'] = {
                    'success': True,
                    'jobs_fetched': jobs_fetched,
                    'skills_updated': skills_updated
                }
                
                self._update_status('running', 'data_fetch', 35,
                    f'✅ Fetched {jobs_fetched} jobs, {skills_updated} skills updated')
                
            except Exception as e:
                error_msg = f"Data fetch failed: {e}"
                logger.error(error_msg)
                results['stages']['data_fetch'] = {'success': False, 'error': str(e)}
                self._update_status('running', 'etl', 35,
                    f'⚠️ Data fetch failed ({e}), continuing with existing data...')
            
            # Small delay between stages
            await asyncio.sleep(1)
            
            # ═══════════════════════════════════════════
            # STAGE 2: Run ELT Pipeline
            # ═══════════════════════════════════════════
            self._update_status('running', 'etl', 40,
                '🔄 Stage 2/3: Running ELT pipeline (MongoDB → BigQuery)...')
            
            try:
                from src.etl.mongodb_to_bigquery import MongoDBToBigQueryETL
                etl = MongoDBToBigQueryETL()
                
                etl_results = {}
                
                # Extract and load live jobs to BigQuery Bronze
                jobs_df = etl.extract_live_jobs_from_mongodb()
                if jobs_df is not None and not jobs_df.empty:
                    etl.load_to_bigquery(jobs_df, 'raw_jobs_live', etl.dataset_bronze)
                    etl_results['bronze_jobs'] = len(jobs_df)
                    self._update_status('running', 'etl', 55,
                        f'✅ Loaded {len(jobs_df)} jobs to BigQuery Bronze')
                
                # Extract and load live skills
                skills_df = etl.extract_live_skills_from_mongodb()
                if skills_df is not None and not skills_df.empty:
                    etl.load_to_bigquery(skills_df, 'raw_skills_live', etl.dataset_bronze)
                    etl_results['bronze_skills'] = len(skills_df)
                
                results['stages']['etl'] = {'success': True, **etl_results}
                self._update_status('running', 'etl', 65,
                    f'✅ ELT complete: {etl_results}')
                
            except Exception as e:
                error_msg = f"ELT pipeline failed: {e}"
                logger.error(error_msg)
                results['stages']['etl'] = {'success': False, 'error': str(e)}
                self._update_status('running', 'model_training', 65,
                    f'⚠️ ELT failed ({e}), continuing...')
            
            await asyncio.sleep(1)
            
            # ═══════════════════════════════════════════
            # STAGE 3: Retrain Models (if needed)
            # ═══════════════════════════════════════════
            self._update_status('running', 'model_training', 70,
                '🤖 Stage 3/3: Checking if model retraining is needed...')
            
            try:
                from src.ml.incremental_training import IncrementalModelTrainer
                trainer = IncrementalModelTrainer()
                
                should_retrain = trainer.should_retrain()
                
                if should_retrain:
                    self._update_status('running', 'model_training', 75,
                        '🤖 Retraining ML models with fresh data...')
                    training_results = trainer.train_incremental()
                    results['stages']['model_training'] = {
                        'success': training_results.get('success', False),
                        'retrained': True,
                        **training_results
                    }
                    self._update_status('running', 'model_training', 95,
                        f'✅ Models retrained: {training_results.get("career_model", {}).get("ensemble_accuracy", "N/A")}')
                else:
                    results['stages']['model_training'] = {
                        'success': True,
                        'retrained': False,
                        'reason': 'Models are still fresh'
                    }
                    self._update_status('running', 'model_training', 95,
                        '✅ Models are fresh, no retraining needed')
                    
            except Exception as e:
                error_msg = f"Model training failed: {e}"
                logger.error(error_msg)
                results['stages']['model_training'] = {'success': False, 'error': str(e)}
            
            # ═══════════════════════════════════════════
            # DONE — Save state to MongoDB
            # ═══════════════════════════════════════════
            try:
                if mongodb_client and mongodb_client.db is not None:
                    mongodb_client.db['pipeline_state'].update_one(
                        {'type': 'live_pipeline_state'},
                        {'$set': {
                            'state': {
                                'last_data_fetch': datetime.now().isoformat(),
                                'last_etl_run': datetime.now().isoformat(),
                                'last_model_training': datetime.now().isoformat(),
                                'errors': [],
                                'stats': results
                            },
                            'updated_at': datetime.now().isoformat()
                        }},
                        upsert=True
                    )
            except Exception as e:
                logger.error(f"Failed to save pipeline state: {e}")
            
            self._pipeline_status['completed_at'] = datetime.now().isoformat()
            self._pipeline_status['last_run_result'] = results
            self._update_status('completed', progress=100,
                message='✅ Pipeline complete! Data is fresh.')
            
        except Exception as e:
            error_msg = f"Pipeline failed: {e}"
            self._pipeline_status['error'] = error_msg
            self._update_status('failed', message=error_msg)
            logger.error(error_msg)
            logger.error(traceback.format_exc())
        
        finally:
            self.is_running = False


# Global singleton
_startup_pipeline: Optional[StartupPipeline] = None

def get_startup_pipeline(staleness_hours: float = 2.0) -> StartupPipeline:
    """Get or create the startup pipeline singleton"""
    global _startup_pipeline
    if _startup_pipeline is None:
        _startup_pipeline = StartupPipeline(staleness_hours=staleness_hours)
    return _startup_pipeline
