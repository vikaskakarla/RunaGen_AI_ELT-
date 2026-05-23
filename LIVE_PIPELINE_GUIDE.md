# Live Data Pipeline - Complete Implementation Guide

## 🎯 Overview

This live data pipeline transforms your static ML system into a dynamic, continuously updating platform that:
- Fetches fresh job data hourly from APIs
- Processes data through ELT pipeline every 4 hours
- Retrains ML models daily with new data
- Serves live predictions through API
- Updates dashboards with real-time market insights

---

## 📊 How the Live Pipeline Works

### Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     LIVE DATA PIPELINE                          │
└─────────────────────────────────────────────────────────────────┘

1. DATA INGESTION (Hourly)
   ├─ Adzuna API → Fetch 200 jobs
   ├─ Indeed Scraper → Fetch additional jobs
   └─ Store in MongoDB (live_jobs, live_skills collections)

2. ETL PROCESSING (Every 4 hours)
   ├─ Extract: MongoDB → Pandas DataFrames
   ├─ Transform: dbt (Bronze → Silver → Gold)
   └─ Load: BigQuery Data Warehouse

3. MODEL TRAINING (Daily at 2 AM)
   ├─ Check if retraining needed (500+ new samples OR 7+ days old)
   ├─ Load fresh data from BigQuery + MongoDB
   ├─ Train ensemble models (Career + Salary)
   └─ Deploy new models (versioned)

4. API SERVING (Real-time)
   ├─ Serve predictions using latest models
   ├─ Fetch live job recommendations
   └─ Provide real-time market insights

5. DASHBOARD REFRESH (Every 6 hours)
   ├─ Update cached statistics
   ├─ Generate market trend reports
   └─ Refresh visualizations
```

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.8+** installed
2. **MongoDB** running (local or cloud)
3. **BigQuery** credentials configured
4. **API Keys** for data sources:
   - Adzuna API (required)
   - Indeed (optional)

### Installation

1. **Install dependencies:**
```bash
pip install -r requirements-live.txt
```

2. **Configure environment variables:**
```bash
# .env file
MONGO_URI=mongodb://localhost:27017/
MONGO_DB=runagen_ml_warehouse

# API Keys
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key

# BigQuery
GOOGLE_APPLICATION_CREDENTIALS=credentials/bigquery-key.json
GCP_PROJECT_ID=your-project-id
```

3. **Run the pipeline:**

**Windows:**
```bash
# Development mode (recommended for testing)
run_live_pipeline.bat --development

# Production mode (for deployment)
run_live_pipeline.bat --production

# Run once (for testing)
run_live_pipeline.bat --run-once
```

**Linux/Mac:**
```bash
# Development mode
python run_live_pipeline.py --mode development

# Production mode
python run_live_pipeline.py --mode production

# Run once
python run_live_pipeline.py --run-once
```

---

## ⚙️ Configuration Modes

### Production Mode (Recommended for Deployment)
```
Schedule:
  ⏰ Hourly: Fetch 200 jobs from APIs
  ⏰ Every 4 hours: Run ETL pipeline
  ⏰ Daily at 2 AM: Full model retraining
  ⏰ Every 6 hours: Dashboard refresh
  ⏰ Every 30 minutes: Health check & cleanup

Use Case: Production deployment, live website
```

### Development Mode (Recommended for Testing)
```
Schedule:
  ⏰ Every 2 hours: Fetch 100 jobs
  ⏰ Every 6 hours: Run ETL pipeline
  ⏰ Daily at 3 AM: Model retraining

Use Case: Local development, testing
```

### Testing Mode (For Rapid Iteration)
```
Schedule:
  ⏰ Every 30 minutes: Fetch 50 jobs
  ⏰ Every 2 hours: Run ETL pipeline
  ⏰ Every 4 hours: Model retraining

Use Case: Debugging, rapid testing
```

---

## 📁 New Files Created

### Core Pipeline Files

1. **`src/etl/live_data_ingestion.py`**
   - Fetches data from Adzuna API
   - Stores in MongoDB (live_jobs, live_skills)
   - Handles deduplication and data quality

2. **`src/scheduler/live_pipeline_scheduler.py`**
   - Main scheduler orchestrating all pipeline stages
   - Manages job scheduling with APScheduler
   - Handles error recovery and health monitoring

3. **`src/ml/incremental_training.py`**
   - Incremental model training logic
   - Model versioning and storage
   - Data validation and quality checks

4. **`src/api/live_endpoints.py`**
   - Live data API endpoints
   - Real-time market insights
   - Pipeline health monitoring

### Runner Scripts

5. **`run_live_pipeline.py`**
   - Main entry point for pipeline
   - Command-line interface
   - Logging and error handling

6. **`run_live_pipeline.bat`**
   - Windows batch script
   - Easy startup for Windows users

### Documentation

7. **`LIVE_PIPELINE_GUIDE.md`** (this file)
   - Complete implementation guide
   - Architecture documentation

8. **`requirements-live.txt`**
   - Additional dependencies for live pipeline

---

## 🔌 API Endpoints

### Live Data Endpoints

All endpoints are prefixed with `/api/live/`

#### 1. Pipeline Status
```http
GET /api/live/status
```
Returns:
- Live mode status
- Last data update timestamp
- Data freshness (hours)
- Total jobs and skills
- Pipeline health

#### 2. Recent Jobs
```http
GET /api/live/jobs/recent?limit=50&hours=24
```
Returns recent jobs from live data

#### 3. Trending Skills
```http
GET /api/live/skills/trending?limit=20
```
Returns currently trending skills

#### 4. Market Trends
```http
GET /api/live/market-trends
```
Returns:
- Top locations
- Top companies
- Salary insights
- Top skills

#### 5. Dashboard Data
```http
GET /api/live/dashboard-data
```
Returns comprehensive data for dashboards (cached)

#### 6. Pipeline Health
```http
GET /api/live/pipeline-health
```
Returns detailed health information

#### 7. Manual Trigger (Admin)
```http
POST /api/live/trigger-data-fetch?limit=100
```
Manually trigger data fetch

---

## 🗄️ Database Schema

### MongoDB Collections

#### `live_jobs`
```javascript
{
  _id: ObjectId,
  title: String,
  company: String,
  location: String,
  salary_min: Number,
  salary_max: Number,
  currency: String,
  description: String,
  skills: [String],
  experience_required: String,
  job_type: String,
  posted_date: Date,
  source: String,  // 'adzuna', 'indeed', etc.
  source_id: String,
  url: String,
  ingested_at: Date,
  is_active: Boolean
}
```

#### `live_skills`
```javascript
{
  _id: ObjectId,
  skill_name: String,
  demand_count: Number,
  total_mentions: Number,
  is_trending: Boolean,
  last_seen: Date,
  source: String
}
```

#### `pipeline_state`
```javascript
{
  type: 'live_pipeline_state',
  state: {
    last_data_fetch: ISODate,
    last_etl_run: ISODate,
    last_model_training: ISODate,
    errors: [
      {
        timestamp: ISODate,
        stage: String,
        error: String
      }
    ],
    stats: Object
  },
  updated_at: ISODate
}
```

#### `dashboard_cache`
```javascript
{
  type: 'live_dashboard_data',
  timestamp: ISODate,
  summary_stats: Object,
  market_trends: Object,
  data_sources: Array
}
```

### BigQuery Tables

#### `runagen_bronze.raw_jobs_live`
- Same schema as `raw_jobs`
- Contains live-fetched job data
- Marked with `is_live: true`

#### `runagen_bronze.raw_skills_live`
- Same schema as `raw_skills`
- Contains live-extracted skills
- Marked with `is_live: true`

---

## 🔄 Data Flow Details

### 1. Data Ingestion Flow

```python
# Hourly execution
LiveDataIngestion.fetch_all_live_data(limit=200)
  ├─ AdzunaAPIClient.fetch_jobs()
  │   ├─ Call Adzuna API
  │   ├─ Parse job data
  │   └─ Extract skills from descriptions
  ├─ Store in MongoDB (live_jobs)
  ├─ Extract unique skills
  └─ Store in MongoDB (live_skills)
```

### 2. ETL Pipeline Flow

```python
# Every 4 hours
LivePipelineScheduler.run_etl_pipeline()
  ├─ Extract live jobs from MongoDB
  ├─ Extract live skills from MongoDB
  ├─ Load to BigQuery Bronze layer
  ├─ Run dbt transformations
  │   ├─ Bronze → Silver (cleaning)
  │   └─ Silver → Gold (aggregations)
  └─ Validate data quality
```

### 3. Model Training Flow

```python
# Daily at 2 AM
IncrementalModelTrainer.train_incremental()
  ├─ Check if retraining needed
  │   ├─ 500+ new samples? OR
  │   └─ 7+ days since last training?
  ├─ Load training data
  │   ├─ BigQuery (historical)
  │   └─ MongoDB (recent live data)
  ├─ Train Career Model (Ensemble)
  │   ├─ Random Forest
  │   ├─ Gradient Boosting
  │   └─ Average predictions
  ├─ Train Salary Model
  ├─ Validate models
  └─ Deploy new versions
```

### 4. API Serving Flow

```python
# Real-time
FastAPI.analyze_resume()
  ├─ Extract skills from resume
  ├─ Predict career (using latest model)
  ├─ Predict salary (using latest model)
  ├─ Fetch live job recommendations
  │   ├─ Priority 1: MongoDB live_jobs
  │   ├─ Priority 2: BigQuery historical
  │   └─ Priority 3: Adzuna API (fallback)
  └─ Return comprehensive analysis
```

---

## 📊 Monitoring & Health Checks

### Health Check Endpoint

```bash
curl http://localhost:8000/api/live/pipeline-health
```

Response:
```json
{
  "overall_status": "healthy",
  "last_data_fetch": "2024-01-15T10:00:00",
  "last_etl_run": "2024-01-15T08:00:00",
  "last_model_training": "2024-01-15T02:00:00",
  "error_count_24h": 0,
  "data_freshness_hours": 1.5,
  "components": {
    "data_ingestion": "healthy",
    "etl_pipeline": "healthy",
    "model_training": "healthy",
    "mongodb": "healthy"
  }
}
```

### Log Files

- **`logs/live_pipeline.log`** - Main pipeline logs
- **`logs/data_ingestion.log`** - Data fetch logs
- **`logs/model_training.log`** - Training logs

---

## 🐛 Troubleshooting

### Common Issues

#### 1. "Adzuna API credentials not found"
**Solution:** Add to `.env`:
```bash
ADZUNA_APP_ID=your_app_id
ADZUNA_APP_KEY=your_app_key
```

#### 2. "MongoDB connection failed"
**Solution:** 
- Check MongoDB is running: `mongod --version`
- Verify MONGO_URI in `.env`
- Test connection: `mongo mongodb://localhost:27017/`

#### 3. "BigQuery authentication failed"
**Solution:**
- Verify credentials file exists: `credentials/bigquery-key.json`
- Check GCP_PROJECT_ID in `.env`
- Test: `gcloud auth application-default login`

#### 4. "No new data being fetched"
**Solution:**
- Check Adzuna API quota
- Verify API keys are valid
- Check logs: `logs/live_pipeline.log`

#### 5. "Models not retraining"
**Solution:**
- Check if threshold met (500+ samples OR 7+ days)
- Verify data quality
- Check logs: `logs/model_training.log`

---

## 🔧 Advanced Configuration

### Custom Scheduling

Edit `src/scheduler/live_pipeline_scheduler.py`:

```python
# Change data fetch frequency
self.scheduler.add_job(
    self.fetch_live_data,
    IntervalTrigger(hours=1),  # Change to hours=2 for every 2 hours
    kwargs={'limit': 200}
)

# Change model retraining time
self.scheduler.add_job(
    self.retrain_models,
    CronTrigger(hour=2, minute=0),  # Change hour to desired time
)
```

### Custom Data Sources

Add new data source in `src/etl/live_data_ingestion.py`:

```python
class CustomAPIClient:
    def fetch_jobs(self, limit: int) -> List[JobData]:
        # Your implementation
        pass

# In LiveDataIngestion class
def fetch_all_live_data(self, total_limit: int):
    # Add your custom source
    custom_jobs = self.custom_client.fetch_jobs(limit=100)
    self._store_jobs_in_mongodb(custom_jobs, 'custom_source')
```

### Model Training Thresholds

Edit `src/ml/incremental_training.py`:

```python
class IncrementalModelTrainer:
    def __init__(self):
        self.retrain_threshold_samples = 500  # Change to 1000 for less frequent
        self.retrain_threshold_days = 7       # Change to 14 for bi-weekly
```

---

## 📈 Performance Optimization

### 1. Database Indexing

```javascript
// MongoDB indexes for better performance
db.live_jobs.createIndex({ "ingested_at": -1 })
db.live_jobs.createIndex({ "is_active": 1, "ingested_at": -1 })
db.live_jobs.createIndex({ "title": "text", "description": "text" })
db.live_skills.createIndex({ "skill_name": 1 })
db.live_skills.createIndex({ "is_trending": 1, "demand_count": -1 })
```

### 2. Caching

The pipeline automatically caches:
- Dashboard data (1 hour TTL)
- Market trends (6 hours TTL)
- Pipeline state (real-time)

### 3. Batch Processing

Data is processed in batches:
- MongoDB queries: 5000 records/batch
- BigQuery loads: 5000 rows/batch
- API fetches: 50 jobs/request (Adzuna limit)

---

## 🚀 Deployment

### Local Development

```bash
python run_live_pipeline.py --mode development
```

### Production Server

1. **Using systemd (Linux):**

Create `/etc/systemd/system/live-pipeline.service`:
```ini
[Unit]
Description=RunaGen Live Data Pipeline
After=network.target mongodb.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/elt
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python run_live_pipeline.py --mode production
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable live-pipeline
sudo systemctl start live-pipeline
sudo systemctl status live-pipeline
```

2. **Using Docker:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements-live.txt

CMD ["python", "run_live_pipeline.py", "--mode", "production"]
```

Build and run:
```bash
docker build -t live-pipeline .
docker run -d --name live-pipeline \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  live-pipeline
```

3. **Using PM2 (Node.js process manager):**

```bash
pm2 start run_live_pipeline.py --name live-pipeline --interpreter python3 -- --mode production
pm2 save
pm2 startup
```

### Cloud Deployment

#### Google Cloud Run

```bash
gcloud run deploy live-pipeline \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars MONGO_URI=$MONGO_URI,ADZUNA_APP_ID=$ADZUNA_APP_ID
```

#### AWS EC2

1. Launch EC2 instance
2. Install dependencies
3. Setup systemd service (see above)
4. Configure security groups for MongoDB access

---

## 📊 Metrics & Analytics

### Key Metrics to Monitor

1. **Data Ingestion:**
   - Jobs fetched per hour
   - API success rate
   - Data quality score

2. **ETL Pipeline:**
   - Processing time
   - Data volume (Bronze → Silver → Gold)
   - Transformation success rate

3. **Model Training:**
   - Training frequency
   - Model accuracy trends
   - Training duration

4. **API Performance:**
   - Response time
   - Prediction accuracy
   - Live data freshness

### Accessing Metrics

```python
# Get pipeline statistics
from src.etl.live_data_ingestion import LiveDataIngestion

ingestion = LiveDataIngestion()
stats = ingestion.get_ingestion_stats()

print(f"Total jobs: {stats['total_jobs']}")
print(f"Recent jobs (24h): {stats['recent_jobs_24h']}")
print(f"Trending skills: {stats['trending_skills']}")
```

---

## 🎓 Best Practices

1. **Start with Development Mode**
   - Test thoroughly before production
   - Monitor logs for errors
   - Validate data quality

2. **Monitor API Quotas**
   - Adzuna: 1000 requests/month (free tier)
   - Implement rate limiting
   - Cache API responses

3. **Regular Backups**
   - MongoDB: Daily backups
   - Model artifacts: Version control
   - Configuration: Git repository

4. **Error Handling**
   - Pipeline continues on non-critical errors
   - Errors logged to MongoDB
   - Email alerts for critical failures

5. **Data Quality**
   - Validate before loading to BigQuery
   - Remove duplicates
   - Handle missing values

---

## 📞 Support & Maintenance

### Regular Maintenance Tasks

- **Daily:** Check pipeline health
- **Weekly:** Review error logs
- **Monthly:** Analyze model performance
- **Quarterly:** Update dependencies

### Getting Help

- Check logs: `logs/live_pipeline.log`
- Review error collection in MongoDB
- Test individual components:
  ```bash
  python -m src.etl.live_data_ingestion
  python -m src.ml.incremental_training
  ```

---

## 🎉 Success Indicators

Your live pipeline is working correctly when:

✅ Data freshness < 2 hours
✅ New jobs appearing in MongoDB hourly
✅ Models retraining automatically
✅ API serving live job recommendations
✅ Dashboard showing real-time trends
✅ Zero critical errors in last 24 hours

---

## 📝 Next Steps

1. **Run the pipeline:**
   ```bash
   run_live_pipeline.bat --development
   ```

2. **Test API endpoints:**
   ```bash
   curl http://localhost:8000/api/live/status
   ```

3. **Monitor logs:**
   ```bash
   tail -f logs/live_pipeline.log
   ```

4. **Check dashboard:**
   - Open `http://localhost:8000/dashboards/html/index.html`
   - Verify live data indicators

5. **Deploy to production:**
   - Switch to production mode
   - Setup monitoring
   - Configure alerts

---

## 🏆 Conclusion

You now have a fully functional live data pipeline that:
- ✅ Fetches fresh data automatically
- ✅ Processes data through ELT pipeline
- ✅ Retrains ML models with new data
- ✅ Serves live predictions via API
- ✅ Updates dashboards in real-time

Your static ML system is now **LIVE**! 🚀

---

**Version:** 1.0.0  
**Last Updated:** 2024  
**Author:** RunaGen AI Team