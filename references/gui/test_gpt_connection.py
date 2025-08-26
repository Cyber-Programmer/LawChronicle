#!/usr/bin/env python3
"""
Simple GPT Connection Test Script

This script tests the Azure OpenAI connection independently to help debug
the JSON parsing issues in the main GUI.
"""

import json
import os
import sys

# Add parent directory to path for utils imports
parent_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(parent_dir)

def test_gpt_connection():
    """Test GPT connection with minimal setup"""
    
    # Load configuration
    config_file = "gui/config_intelligent_grouping.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        print("✅ Config loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return False
    
    # Check Azure OpenAI configuration
    azure_config = config.get("azure_openai", {})
    required_keys = ["api_key", "endpoint", "api_version", "model"]
    missing_keys = [key for key in required_keys if not azure_config.get(key)]
    
    if missing_keys:
        print(f"❌ Missing Azure OpenAI config keys: {missing_keys}")
        return False
    
    print("✅ Azure OpenAI config complete")
    
    # Try to import Azure OpenAI
    try:
        from openai import AzureOpenAI
        print("✅ Azure OpenAI imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import Azure OpenAI: {e}")
        return False
    
    # Test connection
    try:
        client = AzureOpenAI(
            api_key=azure_config["api_key"],
            api_version=azure_config["api_version"],
            azure_endpoint=azure_config["endpoint"]
        )
        print("✅ Azure OpenAI client created")
    except Exception as e:
        print(f"❌ Failed to create Azure OpenAI client: {e}")
        return False
    
    # Test simple API call
    test_prompt = """
    Respond with this exact JSON: {"test": "success", "message": "GPT connection working"}
    
    IMPORTANT: Respond ONLY with valid JSON. Do not include any other text.
    """
    
    try:
        print("🧪 Testing GPT API call...")
        response = client.chat.completions.create(
            model=azure_config["model"],
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Always respond with valid JSON only."},
                {"role": "user", "content": test_prompt}
            ],
            temperature=0.1,
            max_tokens=100
        )
        
        content = response.choices[0].message.content.strip()
        print(f"📝 Raw GPT Response: {repr(content)}")
        print(f"📝 Response length: {len(content)} characters")
        
        # Try to parse JSON
        try:
            result = json.loads(content)
            print(f"✅ JSON parsing successful: {result}")
            return True
        except json.JSONDecodeError as json_error:
            print(f"❌ JSON parsing failed: {json_error}")
            print(f"❌ Error at line {json_error.lineno}, column {json_error.colno}")
            
            # Try to find JSON-like content
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                print(f"🔍 Found JSON-like content: {json_match.group()}")
                try:
                    result = json.loads(json_match.group())
                    print(f"✅ Extracted JSON successful: {result}")
                    return True
                except json.JSONDecodeError:
                    print("❌ Extracted content still not valid JSON")
            else:
                print("🔍 No JSON-like content found in response")
            
            return False
            
    except Exception as e:
        print(f"❌ GPT API call failed: {e}")
        print(f"❌ Exception type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    print("🧪 Testing GPT Connection...")
    print("=" * 50)
    
    success = test_gpt_connection()
    
    print("=" * 50)
    if success:
        print("✅ GPT connection test PASSED")
    else:
        print("❌ GPT connection test FAILED")
