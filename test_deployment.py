"""
Test deployment - Verify all components are working
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("\n1️⃣ Testing Health Endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        data = response.json()
        
        print(f"   Status: {data['status']}")
        print(f"   Version: {data['version']}")
        print(f"   Model Accuracy: {data['model_accuracy']}%")
        print(f"   Career Model Loaded: {data['models_loaded']['career']}")
        print(f"   Salary Model Loaded: {data['models_loaded']['salary']}")
        
        if data['model_accuracy'] >= 92.70:
            print("   ✅ Health check passed!")
            return True
        else:
            print("   ❌ Model accuracy below 92.70%")
            return False
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return False


def test_trending_skills():
    """Test trending skills endpoint"""
    print("\n2️⃣ Testing Trending Skills...")
    try:
        response = requests.get(f"{BASE_URL}/api/skill-trends/trending?role=Data%20Scientist&limit=5")
        data = response.json()
        
        if data['status'] == 'success':
            print(f"   Role: {data['role']}")
            print(f"   Found {len(data['trending_skills'])} trending skills")
            print(f"   Top 3 skills:")
            for skill in data['trending_skills'][:3]:
                print(f"      - {skill['skill_name']}: {skill['demand_count']} jobs")
            print("   ✅ Trending skills test passed!")
            return True
        else:
            print(f"   ❌ Failed: {data}")
            return False
    except Exception as e:
        print(f"   ❌ Trending skills test failed: {e}")
        return False


def test_learning_path():
    """Test learning path generation"""
    print("\n3️⃣ Testing Learning Path Generation...")
    try:
        payload = {
            "career": "Data Scientist",
            "current_skills": ["Python", "SQL"],
            "target_level": "intermediate",
            "weeks_available": 12
        }
        
        response = requests.post(
            f"{BASE_URL}/api/learning-path",
            json=payload
        )
        data = response.json()
        
        if data['status'] == 'success':
            lp = data['learning_path']
            print(f"   Career: {data['career']}")
            print(f"   Total Hours: {lp['total_hours_required']}")
            print(f"   Estimated Weeks: {lp['estimated_weeks']}")
            print(f"   Skills to Learn: {len(lp['skills_to_learn'])}")
            print("   ✅ Learning path test passed!")
            return True
        else:
            print(f"   ❌ Failed: {data}")
            return False
    except Exception as e:
        print(f"   ❌ Learning path test failed: {e}")
        return False


def test_job_scraping():
    """Test job scraping"""
    print("\n4️⃣ Testing Job Scraping...")
    try:
        response = requests.get(f"{BASE_URL}/api/jobs/scrape?keywords=python,data&location=India")
        data = response.json()
        
        if data['status'] == 'success':
            print(f"   Jobs Found: {data['jobs_found']}")
            print(f"   Source: {data['source']}")
            if data['jobs']:
                print(f"   Sample Job: {data['jobs'][0]['title']} at {data['jobs'][0]['company']}")
            print("   ✅ Job scraping test passed!")
            return True
        else:
            print(f"   ❌ Failed: {data}")
            return False
    except Exception as e:
        print(f"   ❌ Job scraping test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("="*70)
    print("🧪 DEPLOYMENT TESTING")
    print("="*70)
    print(f"Testing API at: {BASE_URL}")
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    results.append(("Trending Skills", test_trending_skills()))
    results.append(("Learning Path", test_learning_path()))
    results.append(("Job Scraping", test_job_scraping()))
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")
    
    print(f"\n   Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n   🎉 ALL TESTS PASSED! Deployment is ready!")
    else:
        print(f"\n   ⚠️  {total - passed} test(s) failed. Please check the logs.")
    
    print("="*70)


if __name__ == "__main__":
    main()
