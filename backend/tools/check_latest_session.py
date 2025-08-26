#!/usr/bin/env python3
"""
Check latest search session
"""

import requests

def check_latest_session():
    """Check the details of the latest search session"""
    
    try:
        response = requests.get('http://localhost:8000/api/v1/phase4/search/search-sessions')
        data = response.json()
        
        if data['sessions']:
            latest = data['sessions'][0]  # Most recent
            
            print("🔍 Latest Search Session Details")
            print("=" * 40)
            print(f"📋 Session ID: {latest['session_id']}")
            print(f"📊 Total documents: {latest['total_documents']}")
            print(f"📅 Status: {latest['status']}")
            print(f"🗂️ Source collections: {latest['metadata']['source_collections']}")
            print(f"🤖 AI processed: {latest['metadata']['ai_processed']}")
            print(f"🎯 High confidence: {latest['metadata']['high_confidence']}")
            
            if latest['total_documents'] == 0:
                print("\n❌ ISSUE: Session has 0 documents")
                print("   This indicates the search isn't finding matching documents")
            else:
                print(f"\n✅ SUCCESS: Session found {latest['total_documents']} documents")
        else:
            print("No search sessions found")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_latest_session()
