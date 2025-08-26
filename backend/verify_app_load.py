"""
Simple script to verify the backend loads correctly with new endpoints
"""
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from main import app
    from fastapi.openapi.utils import get_openapi
    
    print("✅ Main app imported successfully")
    
    # Get OpenAPI spec
    spec = get_openapi(
        title=app.title, 
        version=app.version, 
        openapi_version=app.openapi_version, 
        description=app.description, 
        routes=app.routes
    )
    
    # Check for our new endpoints
    phase2_paths = [path for path in spec["paths"] if "phase2" in path]
    sorting_endpoint = "/api/v1/phase2/apply-sorting" in spec["paths"]
    cleaning_endpoint = "/api/v1/phase2/apply-cleaning" in spec["paths"]
    
    print(f"📋 Found {len(phase2_paths)} Phase 2 endpoints")
    print(f"🔄 Sorting endpoint exists: {sorting_endpoint}")
    print(f"🧹 Cleaning endpoint exists: {cleaning_endpoint}")
    
    if sorting_endpoint and cleaning_endpoint:
        print("🎉 All new endpoints are properly loaded!")
    else:
        print("❌ Some endpoints are missing")
    
    # Show all Phase 2 endpoints
    print("\n📍 All Phase 2 endpoints:")
    for path in sorted(phase2_paths):
        methods = list(spec["paths"][path].keys())
        print(f"  {path} ({', '.join(methods).upper()})")

except Exception as e:
    print(f"❌ Error loading app: {e}")
    import traceback
    traceback.print_exc()
