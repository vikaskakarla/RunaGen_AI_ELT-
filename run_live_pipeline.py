"""
Live Pipeline Runner
Main entry point for running the live data pipeline
"""
import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.scheduler.live_pipeline_scheduler import LivePipelineScheduler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/live_pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def print_banner():
    """Print startup banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║           🚀 LIVE DATA PIPELINE - RUNAGEN AI 🚀              ║
    ║                                                               ║
    ║   Real-time Job Market Intelligence & ML Model Training      ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Live Data Pipeline Scheduler',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in production mode (recommended for deployment)
  python run_live_pipeline.py --mode production

  # Run in development mode (more frequent updates)
  python run_live_pipeline.py --mode development

  # Run in testing mode (very frequent updates)
  python run_live_pipeline.py --mode testing

  # Run pipeline once and exit
  python run_live_pipeline.py --run-once

  # Run with custom log level
  python run_live_pipeline.py --mode production --log-level DEBUG

Schedule Details:
  Production Mode:
    - Hourly: Fetch fresh data from APIs (200 jobs)
    - Every 4 hours: Run ETL pipeline
    - Daily at 2 AM: Full model retraining
    - Every 6 hours: Dashboard data refresh
    - Every 30 minutes: Health check

  Development Mode:
    - Every 2 hours: Fetch data (100 jobs)
    - Every 6 hours: Run ETL pipeline
    - Daily at 3 AM: Model retraining

  Testing Mode:
    - Every 30 minutes: Fetch data (50 jobs)
    - Every 2 hours: Run ETL pipeline
    - Every 4 hours: Model retraining
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['production', 'development', 'testing'],
        default='development',
        help='Scheduler mode (default: development)'
    )
    
    parser.add_argument(
        '--run-once',
        action='store_true',
        help='Run pipeline once and exit (useful for testing)'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--no-initial-run',
        action='store_true',
        help='Skip initial pipeline run on startup'
    )
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Print banner
    print_banner()
    
    # Create logs directory if it doesn't exist
    Path('logs').mkdir(exist_ok=True)
    
    logger.info(f"Starting Live Pipeline in {args.mode.upper()} mode")
    logger.info(f"Log level: {args.log_level}")
    
    # Create scheduler
    scheduler = LivePipelineScheduler(mode=args.mode)
    
    try:
        if args.run_once:
            # Run pipeline once
            logger.info("=" * 70)
            logger.info("RUNNING PIPELINE ONCE")
            logger.info("=" * 70)
            
            logger.info("\n[1/3] Fetching live data...")
            await scheduler.fetch_live_data(limit=100)
            
            logger.info("\n[2/3] Running ETL pipeline...")
            await scheduler.run_etl_pipeline()
            
            logger.info("\n[3/3] Training models...")
            await scheduler.retrain_models()
            
            logger.info("\n" + "=" * 70)
            logger.info("PIPELINE RUN COMPLETED")
            logger.info("=" * 70)
            
            # Show status
            status = scheduler.get_status()
            logger.info("\nPipeline Status:")
            logger.info(f"  Mode: {status['mode']}")
            logger.info(f"  Last Data Fetch: {status['pipeline_state'].get('last_data_fetch', 'N/A')}")
            logger.info(f"  Last ETL Run: {status['pipeline_state'].get('last_etl_run', 'N/A')}")
            logger.info(f"  Last Model Training: {status['pipeline_state'].get('last_model_training', 'N/A')}")
            
        else:
            # Start continuous scheduling
            logger.info("=" * 70)
            logger.info("STARTING CONTINUOUS SCHEDULER")
            logger.info("=" * 70)
            logger.info(f"\nSchedule Configuration ({args.mode} mode):")
            
            if args.mode == 'production':
                logger.info("  ⏰ Hourly: Fetch live data (200 jobs)")
                logger.info("  ⏰ Every 4 hours: Run ETL pipeline")
                logger.info("  ⏰ Daily at 2 AM: Full model retraining")
                logger.info("  ⏰ Every 6 hours: Dashboard refresh")
                logger.info("  ⏰ Every 30 minutes: Health check")
            elif args.mode == 'development':
                logger.info("  ⏰ Every 2 hours: Fetch live data (100 jobs)")
                logger.info("  ⏰ Every 6 hours: Run ETL pipeline")
                logger.info("  ⏰ Daily at 3 AM: Model retraining")
            elif args.mode == 'testing':
                logger.info("  ⏰ Every 30 minutes: Fetch live data (50 jobs)")
                logger.info("  ⏰ Every 2 hours: Run ETL pipeline")
                logger.info("  ⏰ Every 4 hours: Model retraining")
            
            logger.info("\n" + "=" * 70)
            logger.info("Press Ctrl+C to stop the scheduler")
            logger.info("=" * 70 + "\n")
            
            # Start scheduler
            scheduler.start()
            
            # Run initial pipeline if not disabled
            if not args.no_initial_run:
                logger.info("Running initial data fetch...")
                await scheduler.fetch_live_data(limit=100)
            
            # Keep running
            while True:
                await asyncio.sleep(60)
                
                # Periodically log status
                if asyncio.get_event_loop().time() % 3600 < 60:  # Every hour
                    status = scheduler.get_status()
                    logger.info(f"Scheduler Status: {len(status['scheduled_jobs'])} jobs scheduled")
                
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 70)
        logger.info("SHUTDOWN SIGNAL RECEIVED")
        logger.info("=" * 70)
        logger.info("Stopping scheduler gracefully...")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        try:
            scheduler.stop()
            logger.info("Scheduler stopped successfully")
        except:
            pass
        
        logger.info("\n" + "=" * 70)
        logger.info("LIVE PIPELINE SHUTDOWN COMPLETE")
        logger.info("=" * 70)

if __name__ == "__main__":
    # Run async main
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)