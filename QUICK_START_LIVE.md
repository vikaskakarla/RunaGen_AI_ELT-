# 🚀 Quick Start - Live Data Pipeline

## What You're Getting

Transform your static ML system into a **live, continuously updating platform** in 5 minutes!

### Before (Static)
- ❌ Data never updates
- ❌ Models trained once
- ❌ Stale job recommendations
- ❌ Outdated market insights

### After (Live)
- ✅ Fresh data every hour
- ✅ Models retrain daily
- ✅ Live job recommendations
- ✅ Real-time market trends

---

## ⚡ 5-Minute Setup

### Step 1: Install Dependencies (1 min)

```bash
pip install -r requirements-live.txt
```

### Step 2: Configure API Keys (2 min)

Add to your `.env` file:

```bash
# Adzuna API (Get free key at: https://developer.adzuna.com/)
ADZUNA_APP_ID=your_app_id_here
ADZUNA_APP_KEY=your_app_key_here

# MongoDB (if not already configured)
MONGO_URI=mongodb://localhost:27017/
MONGO_DB=runagen_ml_warehouse

# BigQuery (if not already configured)
GOOGLE_APPLICATION_CREDENTIALS=credentials/bigquery-key.json
GCP_PROJECT_ID=your-project-id
```

### Step 3: Run the Pipeline (2 min)

**Windows:**
```bash
run_live_pipeline.bat --development
```

**Linux/Mac:**
```bash
python run_live_pipeline.py --mode development
```

That's it! Your pipeline is now running! 🎉

---

## 🎯 What Happens Next

### Immediate (First 5 minutes)
1. Pipeline fetches 100 jobs from Adzuna
2. Stores in MongoDB (`live_jobs` collection)
3. Extracts skills (`live_skills` collection)
4. Shows you the results

### Every 2 Hours (Development Mode)
- Fetches 100 new jobs
- Updates skill trends
- Keeps data fresh

### Every 6 Hours
- Runs full ETL pipeline
- Processes data through Bronze → Silver → Gold
- Loads to BigQuery

### Daily at 3 AM
- Checks if models need retraining
- Trains new models if needed (500+ new samples)
- Deploys updated models automatically

---

## 🔍 Verify It's Working

### 1. Check Pipeline Status

Open your browser:
```
http://localhost:8000/api/live/status
```

You should see:
```json
{
  "live_mode": true,
  "last_data_update": "2024-01-15T10:00:00",
  "data_freshness_hours": 0.5,
  "total_jobs": 100,
  "pipeline_health": "healthy"
}
```

### 2. Check Recent Jobs

```
http://localhost:8000/api/live/jobs/recent?limit=10
```

### 3. Check Trending Skills

```
http://localhost:8000/api/live/skills/trending
```

### 4. Check Logs

```bash
# Windows
type logs\live_pipeline.log

# Linux/Mac
tail -f logs/live_pipeline.log
```

You should see:
```
✓ Fetched 100 jobs from Adzuna
✓ Stored 95 jobs in MongoDB
✓ Updated 45 skills
✓ Live data ingestion completed
```

---

## 🎮 Test Your Live System

### Test 1: Upload a Resume

Your API now returns **live job recommendations**!

```bash
curl -X POST http://localhost:8000/api/analyze-resume \
  -H "Content-Type: application/json" \
  -d '{
    "resume_text": "Software Engineer with 3 years Python experience",
    "experience_years": 3
  }'
```

Response includes:
- Live job recommendations (from last hour!)
- Real-time salary data
- Current market trends

### Test 2: Check Market Trends

```bash
curl http://localhost:8000/api/live/market-trends
```

See:
- Top hiring companies (this week)
- Hottest locations (right now)
- Trending skills (today)
- Average salaries (current)

---

## 📊 Understanding the Schedule

### Development Mode (What You Just Started)

```
⏰ Every 2 hours    → Fetch 100 jobs
⏰ Every 6 hours    → Run ETL pipeline
⏰ Daily at 3 AM    → Retrain models
```

**Perfect for:** Testing, local development

### Production Mode (For Deployment)

```bash
run_live_pipeline.bat --production
```

```
⏰ Every hour       → Fetch 200 jobs
⏰ Every 4 hours    → Run ETL pipeline
⏰ Daily at 2 AM    → Retrain models
⏰ Every 6 hours    → Refresh dashboards
⏰ Every 30 min     → Health checks
```

**Perfect for:** Live website, production deployment

### Testing Mode (For Debugging)

```bash
run_live_pipeline.bat --testing
```

```
⏰ Every 30 min     → Fetch 50 jobs
⏰ Every 2 hours    → Run ETL pipeline
⏰ Every 4 hours    → Retrain models
```

**Perfect for:** Rapid testing, debugging

---

## 🛠️ Common Commands

### Run Once (Test Without Scheduling)

```bash
python run_live_pipeline.py --run-once
```

This will:
1. Fetch data once
2. Run ETL once
3. Train models once
4. Exit

Perfect for testing!

### Check What's Running

```bash
# Check MongoDB
mongo
> use runagen_ml_warehouse
> db.live_jobs.count()
> db.live_skills.count()
```

### Stop the Pipeline

Press `Ctrl+C` in the terminal

The pipeline will:
1. Finish current task
2. Save state
3. Shutdown gracefully

---

## 🐛 Troubleshooting

### "Adzuna API credentials not found"

**Fix:** Add to `.env`:
```bash
ADZUNA_APP_ID=your_id
ADZUNA_APP_KEY=your_key
```

Get free keys: https://developer.adzuna.com/

### "MongoDB connection failed"

**Fix:** Start MongoDB:
```bash
# Windows
net start MongoDB

# Linux/Mac
sudo systemctl start mongod
```

### "No jobs being fetched"

**Check:**
1. API keys are correct
2. Internet connection works
3. Adzuna API quota not exceeded
4. Check logs: `logs/live_pipeline.log`

### "Models not retraining"

**This is normal!** Models only retrain when:
- 500+ new samples collected, OR
- 7+ days since last training

Force retraining:
```bash
python -m src.ml.incremental_training
```

---

## 📈 What to Expect

### First Hour
- ✅ 100 jobs fetched
- ✅ 40-60 skills extracted
- ✅ Data stored in MongoDB
- ✅ API serving live data

### First Day
- ✅ 1200+ jobs collected (development mode)
- ✅ 200+ unique skills
- ✅ ETL pipeline ran 4 times
- ✅ Data in BigQuery

### First Week
- ✅ 8000+ jobs collected
- ✅ 500+ unique skills
- ✅ Models retrained 1-2 times
- ✅ Dashboards showing trends

---

## 🎯 Next Steps

### 1. Let It Run for 24 Hours

Let the pipeline collect data for a day. You'll see:
- Growing job database
- Emerging skill trends
- Market insights

### 2. Check Your Dashboard

After 24 hours, your dashboards will show:
- Live job market trends
- Real-time skill demand
- Current salary ranges
- Top hiring companies

### 3. Test Resume Analysis

Upload a resume and see:
- Live job recommendations (from today!)
- Current market salary data
- Trending skills to learn

### 4. Deploy to Production

When ready:
```bash
run_live_pipeline.bat --production
```

---

## 🎉 Success Checklist

Your live pipeline is working when you see:

- ✅ Jobs in MongoDB: `db.live_jobs.count()` > 0
- ✅ Skills in MongoDB: `db.live_skills.count()` > 0
- ✅ API status: `http://localhost:8000/api/live/status` shows "healthy"
- ✅ Logs show: "Live data ingestion completed"
- ✅ No errors in last hour

---

## 📚 Learn More

- **Full Guide:** See `LIVE_PIPELINE_GUIDE.md` for complete documentation
- **API Docs:** Visit `http://localhost:8000/docs` for interactive API docs
- **Architecture:** See `LIVE_PIPELINE_GUIDE.md` → "How the Live Pipeline Works"

---

## 💡 Pro Tips

1. **Start Small:** Use development mode first
2. **Monitor Logs:** Keep an eye on `logs/live_pipeline.log`
3. **Check Health:** Visit `/api/live/pipeline-health` regularly
4. **Be Patient:** Models retrain when needed (not immediately)
5. **Test First:** Use `--run-once` to test before continuous running

---

## 🚀 You're Live!

Congratulations! Your ML system is now:
- 🔄 Continuously updating
- 📊 Processing live data
- 🤖 Retraining automatically
- 🌐 Serving real-time insights

**Your static system is now LIVE!** 🎉

---

**Need Help?**
- Check logs: `logs/live_pipeline.log`
- Read full guide: `LIVE_PIPELINE_GUIDE.md`
- Test components individually
- Monitor pipeline health endpoint

**Happy Building!** 🚀