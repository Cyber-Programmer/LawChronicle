#!/usr/bin/env python3
"""
Simple test to verify AI search through the API after field fix
"""

import requests
import json
import time

def test_ai_search_api():
    """Test AI search through the FastAPI endpoint"""
    
    base_url = "http://localhost:8000"
    
    print("🔧 Testing AI Search API with Fixed Field Mapping")
    print("=" * 60)
    
    # Test single collection with limited documents
    payload = {
        "collection_names": ["5batch"],
        "max_docs": 3,
        "output_format": "excel"
    }
    
    print(f"📋 Testing with: {payload}")
    print()
    
    try:
        print("🚀 Starting AI search...")
        response = requests.post(
            f"{base_url}/api/v1/phase4/search/search-dates-ai",
            json=payload,
            timeout=120  # 2 minutes timeout
        )
        
        if response.status_code == 200:
            # Get filename from headers
            content_disposition = response.headers.get('content-disposition', '')
            filename = 'ai_search_results.xlsx'
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"')
            
            # Save the Excel file
            with open(filename, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ SUCCESS: Excel file saved as '{filename}'")
            print(f"📊 File size: {len(response.content)} bytes")
            
            # Try to load the Excel and check content
            try:
                import pandas as pd
                df = pd.read_excel(filename)
                
                print(f"📋 Excel contains {len(df)} rows")
                if len(df) > 0:
                    print("✅ Documents were processed successfully!")
                    print("\n📄 Sample data:")
                    print(df.head(2).to_string())
                else:
                    print("❌ Excel is empty - documents may still not have text content")
                    
            except ImportError:
                print("💡 Install pandas to analyze Excel content: pip install pandas")
            except Exception as e:
                print(f"⚠️ Could not analyze Excel: {e}")
        
        elif response.status_code == 422:
            print("❌ Request validation error:")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend. Is the server running?")
        print("💡 Start with: cd backend && uvicorn main:app --reload")
    except requests.exceptions.Timeout:
        print("⏰ Request timed out - AI processing may take longer")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    test_ai_search_api()
