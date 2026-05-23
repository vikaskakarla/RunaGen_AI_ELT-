"""
Standalone Pipeline Runner (for Windows Task Scheduler)
Runs the data pipeline once and exits.

Usage:
    python run_pipeline_once.py
    python run_pipeline_once.py --limit 100
    python run_pipeline_once.py --skip-etl
    python run_pipeline_once.py --skip-training

This script is designed to be called by Windows Task Scheduler
for background data refreshes even when the web server isn't running.
"""
import asyncio
import argparse
import logging
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Set UTF-8 encoding for stdout/stderr to prevent UnicodeEncodeError on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline_scheduled_run.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('pipeline_once')


def run_pipeline(limit=200, skip_etl=False, skip_training=False):
    """Run the data pipeline synchronously"""
    
    # Create logs directory
    Path('logs').mkdir(exist_ok=True)
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'stages': {},
        'success': True
    }
    
    print("")
    print("=" * 60)
    print("  🚀 RunaGen AI — Scheduled Pipeline Run")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # ── Stage 1: Fetch Data ──
    print("\n[1/3] 📡 Fetching live data from Adzuna API...")
    try:
        from src.etl.live_data_ingestion import LiveDataIngestion
        ingestion = LiveDataIngestion()
        fetch_result = ingestion.fetch_all_live_data(total_limit=limit)
        
        jobs = fetch_result.get('jobs_fetched', 0)
        skills = fetch_result.get('skills_updated', 0)
        results['stages']['data_fetch'] = {'success': True, 'jobs': jobs, 'skills': skills}
        print(f"       ✅ Fetched {jobs} jobs, {skills} skills updated")
        
    except Exception as e:
        print(f"       ❌ Data fetch failed: {e}")
        results['stages']['data_fetch'] = {'success': False, 'error': str(e)}
        results['success'] = False
    
    # ── Stage 2: ELT ──
    if not skip_etl:
        print("\n[2/3] 🔄 Running ELT pipeline (MongoDB → BigQuery)...")
        try:
            from src.etl.mongodb_to_bigquery import MongoDBToBigQueryETL
            etl = MongoDBToBigQueryETL()
            
            etl_stats = {}
            jobs_df = etl.extract_live_jobs_from_mongodb()
            if jobs_df is not None and not jobs_df.empty:
                etl.load_to_bigquery(jobs_df, 'raw_jobs_live', etl.dataset_bronze)
                etl_stats['bronze_jobs'] = len(jobs_df)
            
            skills_df = etl.extract_live_skills_from_mongodb()
            if skills_df is not None and not skills_df.empty:
                etl.load_to_bigquery(skills_df, 'raw_skills_live', etl.dataset_bronze)
                etl_stats['bronze_skills'] = len(skills_df)
            
            results['stages']['etl'] = {'success': True, **etl_stats}
            print(f"       ✅ ELT complete: {etl_stats}")
            
        except Exception as e:
            print(f"       ❌ ELT failed: {e}")
            results['stages']['etl'] = {'success': False, 'error': str(e)}
    else:
        print("\n[2/3] ⏭️  Skipping ELT (--skip-etl)")
        results['stages']['etl'] = {'skipped': True}
    
    # ── Stage 3: Model Training ──
    if not skip_training:
        print("\n[3/3] 🤖 Checking if model retraining is needed...")
        try:
            from src.ml.incremental_training import IncrementalModelTrainer
            trainer = IncrementalModelTrainer()
            
            if trainer.should_retrain():
                print("       Training models with fresh data...")
                train_result = trainer.train_incremental()
                results['stages']['training'] = {'success': True, 'retrained': True, **train_result}
                print(f"       ✅ Models retrained successfully")
            else:
                results['stages']['training'] = {'success': True, 'retrained': False}
                print(f"       ✅ Models are still fresh, no retraining needed")
                
        except Exception as e:
            print(f"       ❌ Training failed: {e}")
            results['stages']['training'] = {'success': False, 'error': str(e)}
    else:
        print("\n[3/3] ⏭️  Skipping training (--skip-training)")
        results['stages']['training'] = {'skipped': True}
    
    # ── Save pipeline state to MongoDB ──
    try:
        from src.utils.mongodb_client import MongoDBClient
        mongo = MongoDBClient()
        if mongo.connect():
            mongo.db['pipeline_state'].update_one(
                {'type': 'live_pipeline_state'},
                {'$set': {
                    'state': {
                        'last_data_fetch': datetime.now().isoformat(),
                        'last_etl_run': datetime.now().isoformat() if not skip_etl else None,
                        'last_model_training': datetime.now().isoformat() if not skip_training else None,
                        'errors': [],
                        'stats': results
                    },
                    'updated_at': datetime.now().isoformat()
                }},
                upsert=True
            )
            print("\n💾 Pipeline state saved to MongoDB")
            mongo.close()
    except Exception as e:
        print(f"\n⚠️  Failed to save pipeline state: {e}")
    
    # ── Summary ──
    print("")
    print("=" * 60)
    status = "✅ SUCCESS" if results['success'] else "⚠️  PARTIAL"
    print(f"  {status} — Pipeline run completed")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Save results to log file
    try:
        log_file = Path('logs') / f"pipeline_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"  Results saved to: {log_file}")
    except Exception:
        pass
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run data pipeline once (for scheduled tasks)')
    parser.add_argument('--limit', type=int, default=200, help='Number of jobs to fetch')
    parser.add_argument('--skip-etl', action='store_true', help='Skip ELT to BigQuery')
    parser.add_argument('--skip-training', action='store_true', help='Skip ML model retraining')
    
    args = parser.parse_args()
    
    run_pipeline(
        limit=args.limit,
        skip_etl=args.skip_etl,
        skip_training=args.skip_training
    )
