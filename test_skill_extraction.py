#!/usr/bin/env python3
"""
Test script for skill extraction
Tests both local (Ollama) and cloud (Gemini) configurations
"""

import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ml.model_1_skill_extraction import SkillExtractor

def test_local_extraction():
    """Test skill extraction with local Ollama"""
    print("\n" + "="*70)
    print("TEST 1: Local Extraction (Ollama)")
    print("="*70)
    
    os.environ["ENVIRONMENT"] = "local"
    os.environ["OLLAMA_URL"] = "http://localhost:11434"
    os.environ["OLLAMA_MODEL"] = "llama3"
    
    extractor = SkillExtractor(use_ollama=True, use_gemini=False)
    
    sample_resume = """
    Senior Software Engineer with 5+ years of experience in Python, AWS, and Docker.
    
    Skills:
    - Python, Java, JavaScript
    - AWS (EC2, S3, Lambda), Azure
    - Docker, Kubernetes
    - PostgreSQL, MongoDB
    - FastAPI, Django, React
    
    Experience:
    - Senior Engineer at TechCorp (2021-2024)
    - Software Engineer at StartupXYZ (2019-2021)
    
    Education:
    - Master's in Computer Science
    """
    
    print("\nExtracting skills from resume...")
    result = extractor.extract_all(sample_resume)
    
    print("\nExtraction Results:")
    print(json.dumps(result, indent=2))
    
    return result

def test_cloud_extraction():
    """Test skill extraction with Gemini API"""
    print("\n" + "="*70)
    print("TEST 2: Cloud Extraction (Gemini)")
    print("="*70)
    
    os.environ["ENVIRONMENT"] = "cloud"
    
    # Check if Gemini API key is set
    if not os.getenv("GEMINI_API_KEY"):
        print("\n⚠️  GEMINI_API_KEY not set. Skipping Gemini test.")
        print("To test Gemini:")
        print("  1. Get API key from https://aistudio.google.com/app/apikey")
        print("  2. Set: export GEMINI_API_KEY=your_key")
        print("  3. Run this script again")
        return None
    
    extractor = SkillExtractor(use_ollama=False, use_gemini=True)
    
    sample_resume = """
    Data Engineer with 3 years of experience in Python, SQL, and AWS.
    
    Skills:
    - Python, SQL, Scala
    - AWS (EMR, S3, Glue), GCP BigQuery
    - Apache Spark, Hadoop
    - ETL, Data Pipelines
    - PostgreSQL, MongoDB, Redis
    
    Experience:
    - Data Engineer at DataCorp (2022-2024)
    - Junior Data Engineer at Analytics Inc (2021-2022)
    
    Education:
    - Bachelor's in Computer Science
    """
    
    print("\nExtracting skills from resume...")
    result = extractor.extract_all(sample_resume)
    
    print("\nExtraction Results:")
    print(json.dumps(result, indent=2))
    
    return result

def test_heuristic_extraction():
    """Test fallback heuristic extraction"""
    print("\n" + "="*70)
    print("TEST 3: Heuristic Extraction (Fallback)")
    print("="*70)
    
    os.environ["ENVIRONMENT"] = "local"
    os.environ["OLLAMA_URL"] = ""  # Disable Ollama
    
    extractor = SkillExtractor(use_ollama=False, use_gemini=False)
    
    sample_resume = """
    Full Stack Developer with expertise in React, Node.js, and MongoDB.
    
    Technical Skills:
    - Frontend: React, Vue.js, HTML/CSS
    - Backend: Node.js, Express, FastAPI
    - Databases: MongoDB, PostgreSQL
    - DevOps: Docker, Kubernetes, CI/CD
    - Cloud: AWS, Google Cloud
    
    Work Experience:
    - Full Stack Developer at WebCorp (2020-2024)
    - Junior Developer at StartupABC (2019-2020)
    
    Education:
    - B.Tech in Information Technology
    """
    
    print("\nExtracting skills from resume (heuristic)...")
    result = extractor.extract_all(sample_resume)
    
    print("\nExtraction Results:")
    print(json.dumps(result, indent=2))
    
    return result

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("RunaGen AI - Skill Extraction Test Suite")
    print("="*70)
    
    results = {}
    
    # Test 1: Heuristic (always works)
    try:
        results["heuristic"] = test_heuristic_extraction()
    except Exception as e:
        print(f"\n❌ Heuristic test failed: {e}")
        results["heuristic"] = None
    
    # Test 2: Local Ollama (if available)
    try:
        results["local"] = test_local_extraction()
    except Exception as e:
        print(f"\n⚠️  Local Ollama test failed: {e}")
        print("   Make sure Ollama is running: ollama serve")
        results["local"] = None
    
    # Test 3: Cloud Gemini (if API key available)
    try:
        results["cloud"] = test_cloud_extraction()
    except Exception as e:
        print(f"\n⚠️  Cloud Gemini test failed: {e}")
        results["cloud"] = None
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, result in results.items():
        if result:
            skills_count = len(result.get("skills", []))
            status = "✅ PASSED" if skills_count > 0 else "⚠️  NO SKILLS EXTRACTED"
            print(f"{test_name.upper():15} {status:20} ({skills_count} skills)")
        else:
            print(f"{test_name.upper():15} ⚠️  SKIPPED")
    
    print("\n" + "="*70)
    print("Recommendations:")
    print("="*70)
    print("1. For local development: Start Ollama with 'ollama serve'")
    print("2. For cloud deployment: Set GEMINI_API_KEY environment variable")
    print("3. Heuristic extraction always works as a fallback")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
