"""
Live Data API Endpoints
Provides real-time data endpoints for the live pipeline
"""
from fastapi import APIRouter, HTTPException, Query, Header
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

from etl.live_data_ingestion import LiveDataIngestion
from utils.mongodb_client import MongoDBClient
from api.bigquery_data_provider import get_data_provider

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/live", tags=["live-data"])

# Initialize components
data_ingestion = LiveDataIngestion()
mongodb_client = MongoDBClient()
data_provider = get_data_provider()

@router.get("/status")
async def get_live_data_status() -> Dict[str, Any]:
    """Get live data pipeline status"""
    try:
        # Get ingestion stats
        ingestion_stats = data_ingestion.get_ingestion_stats()
        
        # Get pipeline state from MongoDB
        pipeline_collection = mongodb_client.get_collection('pipeline_state')
        pipeline_state = pipeline_collection.find_one({'type': 'live_pipeline_state'})
        
        # Calculate data freshness
        last_fetch = None
        data_freshness_hours = None
        
        if pipeline_state and 'state' in pipeline_state:
            last_fetch_str = pipeline_state['state'].get('last_data_fetch')
            if last_fetch_str:
                last_fetch = datetime.fromisoformat(last_fetch_str)
                data_freshness_hours = (datetime.now() - last_fetch).total_seconds() / 3600
        
        return {
            "live_mode": True,
            "last_data_update": last_fetch.isoformat() if last_fetch else None,
            "data_freshness_hours": round(data_freshness_hours, 2) if data_freshness_hours else None,
            "total_jobs": ingestion_stats.get('total_jobs', 0),
            "active_jobs": ingestion_stats.get('active_jobs', 0),
            "recent_jobs_24h": ingestion_stats.get('recent_jobs_24h', 0),
            "total_skills": ingestion_stats.get('total_skills', 0),
            "trending_skills": ingestion_stats.get('trending_skills', 0),
            "source_breakdown": ingestion_stats.get('source_breakdown', []),
            "pipeline_health": "healthy" if data_freshness_hours and data_freshness_hours < 2 else "stale",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting live data status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/recent")
async def get_recent_jobs(
    limit: int = Query(50, ge=1, le=500),
    hours: int = Query(24, ge=1, le=168)  # Max 1 week
) -> Dict[str, Any]:
    """Get recent jobs from live data"""
    try:
        # Get jobs from MongoDB
        jobs_collection = mongodb_client.get_collection('live_jobs')
        
        # Calculate cutoff time
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Query recent jobs
        cursor = jobs_collection.find({
            'ingested_at': {'$gte': cutoff_time},
            'is_active': True
        }).sort('ingested_at', -1).limit(limit)
        
        jobs = []
        for job in cursor:
            jobs.append({
                'id': str(job.get('_id')),
                'title': job.get('title', ''),
                'company': job.get('company', ''),
                'location': job.get('location', ''),
                'salary_min': job.get('salary_min'),
                'salary_max': job.get('salary_max'),
                'currency': job.get('currency', 'INR'),
                'skills': job.get('skills', []),
                'source': job.get('source', ''),
                'posted_date': job.get('posted_date').isoformat() if job.get('posted_date') else None,
                'ingested_at': job.get('ingested_at').isoformat() if job.get('ingested_at') else None,
                'url': job.get('url', '')
            })
        
        return {
            'jobs': jobs,
            'count': len(jobs),
            'hours_back': hours,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting recent jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/skills/trending")
async def get_trending_skills(
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """Get trending skills from live data"""
    try:
        # Get skills from MongoDB
        skills_collection = mongodb_client.get_collection('live_skills')
        
        # Query trending skills
        cursor = skills_collection.find({
            'is_trending': True
        }).sort('demand_count', -1).limit(limit)
        
        skills = []
        for skill in cursor:
            skills.append({
                'id': str(skill.get('_id')),
                'skill_name': skill.get('skill_name', ''),
                'demand_count': skill.get('demand_count', 0),
                'total_mentions': skill.get('total_mentions', 0),
                'last_seen': skill.get('last_seen').isoformat() if skill.get('last_seen') else None,
                'category': skill.get('category', 'Other')
            })
        
        return {
            'trending_skills': skills,
            'count': len(skills),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting trending skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/market-trends")
async def get_live_market_trends() -> Dict[str, Any]:
    """Get live market trends and insights"""
    try:
        # Get recent job data for analysis
        jobs_collection = mongodb_client.get_collection('live_jobs')
        skills_collection = mongodb_client.get_collection('live_skills')
        
        # Get jobs from last 7 days
        cutoff_date = datetime.now() - timedelta(days=7)
        
        # Aggregate job data by location
        location_pipeline = [
            {'$match': {'ingested_at': {'$gte': cutoff_date}, 'is_active': True}},
            {'$group': {'_id': '$location', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': 10}
        ]
        location_trends = list(jobs_collection.aggregate(location_pipeline))
        
        # Aggregate job data by company
        company_pipeline = [
            {'$match': {'ingested_at': {'$gte': cutoff_date}, 'is_active': True}},
            {'$group': {'_id': '$company', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': 10}
        ]
        company_trends = list(jobs_collection.aggregate(company_pipeline))
        
        # Get salary trends (jobs with salary data)
        salary_pipeline = [
            {'$match': {
                'ingested_at': {'$gte': cutoff_date},
                'is_active': True,
                'salary_min': {'$gt': 0}
            }},
            {'$group': {
                '_id': None,
                'avg_salary_min': {'$avg': '$salary_min'},
                'avg_salary_max': {'$avg': '$salary_max'},
                'count': {'$sum': 1}
            }}
        ]
        salary_trends = list(jobs_collection.aggregate(salary_pipeline))
        
        # Get top skills from last 7 days
        top_skills = list(skills_collection.find({
            'last_seen': {'$gte': cutoff_date}
        }).sort('demand_count', -1).limit(15))
        
        # Format response
        market_trends = {
            'top_locations': [
                {'location': item['_id'], 'job_count': item['count']}
                for item in location_trends if item['_id']
            ],
            'top_companies': [
                {'company': item['_id'], 'job_count': item['count']}
                for item in company_trends if item['_id']
            ],
            'salary_insights': {
                'average_min_salary': int(salary_trends[0]['avg_salary_min']) if salary_trends else 0,
                'average_max_salary': int(salary_trends[0]['avg_salary_max']) if salary_trends else 0,
                'jobs_with_salary': salary_trends[0]['count'] if salary_trends else 0,
                'currency': 'INR'
            },
            'top_skills': [
                {
                    'skill_name': skill.get('skill_name', ''),
                    'demand_count': skill.get('demand_count', 0),
                    'is_trending': skill.get('is_trending', False)
                }
                for skill in top_skills
            ],
            'data_period': '7 days',
            'timestamp': datetime.now().isoformat()
        }
        
        return market_trends
        
    except Exception as e:
        logger.error(f"Error getting market trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-data")
async def get_live_dashboard_data() -> Dict[str, Any]:
    """Get comprehensive live data for dashboards"""
    try:
        # Get cached dashboard data from MongoDB
        dashboard_collection = mongodb_client.get_collection('dashboard_cache')
        cached_data = dashboard_collection.find_one({'type': 'live_dashboard_data'})
        
        if cached_data and 'timestamp' in cached_data:
            # Check if cache is fresh (less than 1 hour old)
            cache_time = datetime.fromisoformat(cached_data['timestamp'])
            if (datetime.now() - cache_time).total_seconds() < 3600:  # 1 hour
                return cached_data
        
        # Generate fresh dashboard data
        ingestion_stats = data_ingestion.get_ingestion_stats()
        market_trends = await get_live_market_trends()
        
        dashboard_data = {
            'type': 'live_dashboard_data',
            'timestamp': datetime.now().isoformat(),
            'live_mode': True,
            'summary_stats': {
                'total_jobs': ingestion_stats.get('total_jobs', 0),
                'active_jobs': ingestion_stats.get('active_jobs', 0),
                'recent_jobs_24h': ingestion_stats.get('recent_jobs_24h', 0),
                'total_skills': ingestion_stats.get('total_skills', 0),
                'trending_skills': ingestion_stats.get('trending_skills', 0)
            },
            'market_trends': market_trends,
            'data_sources': ingestion_stats.get('source_breakdown', []),
            'last_updated': ingestion_stats.get('last_updated')
        }
        
        # Cache the data
        dashboard_collection.update_one(
            {'type': 'live_dashboard_data'},
            {'$set': dashboard_data},
            upsert=True
        )
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pipeline-health")
async def get_pipeline_health() -> Dict[str, Any]:
    """Get detailed pipeline health information"""
    try:
        # Get pipeline state
        pipeline_collection = mongodb_client.get_collection('pipeline_state')
        pipeline_state = pipeline_collection.find_one({'type': 'live_pipeline_state'})
        
        # Get health records
        health_collection = mongodb_client.get_collection('pipeline_health')
        latest_health = health_collection.find_one(sort=[('timestamp', -1)])
        
        health_info = {
            'overall_status': 'unknown',
            'last_data_fetch': None,
            'last_etl_run': None,
            'last_model_training': None,
            'error_count_24h': 0,
            'data_freshness_hours': None,
            'components': {
                'data_ingestion': 'unknown',
                'etl_pipeline': 'unknown',
                'model_training': 'unknown',
                'mongodb': 'unknown'
            }
        }
        
        if pipeline_state and 'state' in pipeline_state:
            state = pipeline_state['state']
            
            # Extract timestamps
            health_info['last_data_fetch'] = state.get('last_data_fetch')
            health_info['last_etl_run'] = state.get('last_etl_run')
            health_info['last_model_training'] = state.get('last_model_training')
            
            # Count recent errors
            errors = state.get('errors', [])
            cutoff_time = datetime.now() - timedelta(hours=24)
            recent_errors = [
                e for e in errors
                if datetime.fromisoformat(e['timestamp']) > cutoff_time
            ]
            health_info['error_count_24h'] = len(recent_errors)
            
            # Calculate data freshness
            if health_info['last_data_fetch']:
                last_fetch = datetime.fromisoformat(health_info['last_data_fetch'])
                health_info['data_freshness_hours'] = (datetime.now() - last_fetch).total_seconds() / 3600
        
        # Determine component health
        if health_info['data_freshness_hours'] is not None:
            if health_info['data_freshness_hours'] < 2:
                health_info['components']['data_ingestion'] = 'healthy'
            elif health_info['data_freshness_hours'] < 6:
                health_info['components']['data_ingestion'] = 'warning'
            else:
                health_info['components']['data_ingestion'] = 'error'
        
        # Check MongoDB connection
        try:
            mongodb_client.get_collection('live_jobs').count_documents({}, limit=1)
            health_info['components']['mongodb'] = 'healthy'
        except:
            health_info['components']['mongodb'] = 'error'
        
        # Determine overall status
        component_statuses = list(health_info['components'].values())
        if 'error' in component_statuses:
            health_info['overall_status'] = 'error'
        elif 'warning' in component_statuses:
            health_info['overall_status'] = 'warning'
        elif 'healthy' in component_statuses:
            health_info['overall_status'] = 'healthy'
        
        health_info['timestamp'] = datetime.now().isoformat()
        
        return health_info
        
    except Exception as e:
        logger.error(f"Error getting pipeline health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trigger-data-fetch")
async def trigger_manual_data_fetch(
    limit: int = Query(100, ge=1, le=1000)
) -> Dict[str, Any]:
    """Manually trigger data fetch (for testing/admin use)"""
    try:
        logger.info(f"Manual data fetch triggered with limit: {limit}")
        
        # Run data ingestion
        results = data_ingestion.fetch_all_live_data(total_limit=limit)
        
        return {
            'status': 'completed',
            'results': results,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in manual data fetch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cron/run-pipeline")
async def cron_run_pipeline(
    x_vercel_cron: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Vercel Cron Job endpoint. Triggers the data and model pipeline synchronously.
    Protected by checking x-vercel-cron header.
    """
    import os
    # 1. Security Check
    is_cloud = os.getenv("ENVIRONMENT") == "cloud" or os.getenv("VERCEL") == "1"
    
    if is_cloud and x_vercel_cron != "true":
        logger.warning("Unauthorized attempt to access Vercel Cron endpoint")
        raise HTTPException(
            status_code=401,
            detail="Unauthorized - Only Vercel Cron can trigger this endpoint."
        )
    
    logger.info("⏱️  Cron pipeline trigger started...")
    
    # 2. Execute pipeline synchronously in the request context
    try:
        from scheduler.startup_pipeline import get_startup_pipeline
        pipeline = get_startup_pipeline()
        
        # Check if pipeline is already running to avoid concurrent clashes
        if pipeline.is_running:
            logger.info("Pipeline is already running, skipping cron run.")
            return {
                "status": "skipped",
                "reason": "Pipeline is already running",
                "timestamp": datetime.now().isoformat()
            }
            
        # Ensure MongoDB is connected
        if not mongodb_client.is_connected():
            mongodb_client.connect()
            
        # Run full pipeline synchronously (blocking the request so it runs on Vercel thread)
        await pipeline._run_pipeline(mongodb_client)
        
        status = pipeline.get_status()
        
        if status.get('state') == 'failed':
            return {
                "status": "failed",
                "error": status.get('error'),
                "details": status.get('last_run_result'),
                "timestamp": datetime.now().isoformat()
            }
            
        return {
            "status": "completed",
            "details": status.get('last_run_result'),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cron pipeline run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Add router to main app
def include_live_endpoints(app):
    """Include live endpoints in the main FastAPI app"""
    app.include_router(router)