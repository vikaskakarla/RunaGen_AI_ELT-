"""
Inspect MongoDB Schema to understand the exact structure
"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import json

load_dotenv()

# MongoDB connection
mongo_uri = os.getenv('MONGO_URI', os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'))
mongo_client = MongoClient(mongo_uri)
mongo_db_name = os.getenv('MONGO_DB', os.getenv('MONGODB_DB', 'runagen_db'))
mongo_db = mongo_client[mongo_db_name]

print("="*70)
print("🔍 MONGODB SCHEMA INSPECTOR")
print("="*70)
print(f"\nDatabase: {mongo_db_name}")
print(f"URI: {mongo_uri[:50]}...")

# List all collections
collections = mongo_db.list_collection_names()
print(f"\n📚 Collections found: {len(collections)}")
for coll in collections:
    count = mongo_db[coll].count_documents({})
    print(f"   - {coll}: {count:,} documents")

# Inspect jobs collection
print("\n" + "="*70)
print("📊 JOBS COLLECTION SCHEMA")
print("="*70)

job_collections = ['bronze_jobs', 'jobs', 'silver_jobs']
jobs_coll = None
for coll_name in job_collections:
    if coll_name in collections:
        jobs_coll = mongo_db[coll_name]
        print(f"\nUsing collection: {coll_name}")
        break

if jobs_coll is not None:
    # Get sample document
    sample = jobs_coll.find_one()
    if sample:
        print("\n📄 Sample Document Structure:")
        print(json.dumps(sample, indent=2, default=str))
        
        print("\n🔑 Top-level Keys:")
        for key in sample.keys():
            value = sample[key]
            value_type = type(value).__name__
            if isinstance(value, dict):
                print(f"   - {key}: {value_type} (nested object with {len(value)} keys)")
                print(f"      Sub-keys: {list(value.keys())[:10]}")
            elif isinstance(value, list):
                print(f"   - {key}: {value_type} (array with {len(value)} items)")
            else:
                print(f"   - {key}: {value_type}")
        
        # Check if data is nested
        if 'data' in sample:
            print("\n⚠️  Data is nested under 'data' key!")
            print("   Nested structure keys:", list(sample['data'].keys())[:20])
else:
    print("\n❌ No jobs collection found!")

# Inspect skills collection
print("\n" + "="*70)
print("📊 SKILLS COLLECTION SCHEMA")
print("="*70)

skill_collections = ['bronze_skills', 'skills', 'silver_skills']
skills_coll = None
for coll_name in skill_collections:
    if coll_name in collections:
        skills_coll = mongo_db[coll_name]
        print(f"\nUsing collection: {coll_name}")
        break

if skills_coll is not None:
    sample = skills_coll.find_one()
    if sample:
        print("\n📄 Sample Document Structure:")
        print(json.dumps(sample, indent=2, default=str))
        
        print("\n🔑 Top-level Keys:")
        for key in sample.keys():
            value = sample[key]
            value_type = type(value).__name__
            print(f"   - {key}: {value_type}")
else:
    print("\n❌ No skills collection found!")

print("\n" + "="*70)
print("✅ Inspection Complete!")
print("="*70)
