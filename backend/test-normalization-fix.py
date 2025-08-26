#!/usr/bin/env python3
"""
Test script to verify the normalization logic fix for case sensitivity issues.
This script tests the field name constants and normalization functions.
"""

import sys
import os

# Add both the backend directory and project root to Python path
# This allows us to import from both app modules and the shared module
backend_dir = os.path.dirname(__file__)
project_root = os.path.dirname(backend_dir)  # Go up one level from backend to project root

sys.path.insert(0, project_root)  # Add project root first (for shared module)
sys.path.insert(0, backend_dir)   # Add backend directory (for app modules)

def test_field_name_constants():
    """Test the field name constants and helper functions"""
    print("🧪 Testing field name constants...")
    
    try:
        from app.api.v1.endpoints.phase2 import get_source_field, get_normalized_field
        
        # Test source field names
        assert get_source_field("STATUTE_NAME") == "Statute_Name"
        assert get_source_field("ACT_ORDINANCE") == "Act_Ordinance"
        assert get_source_field("SECTION") == "Section"
        
        # Test normalized field names
        assert get_normalized_field("statute_name") == "statute_name"
        assert get_normalized_field("act_ordinance") == "act_ordinance"
        assert get_normalized_field("section_number") == "section_number"
        
        print("✅ Field name constants working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Field name constants test failed: {e}")
        return False

def test_normalization_functions():
    """Test the normalization functions with various inputs"""
    print("🧪 Testing normalization functions...")
    
    try:
        from app.api.v1.endpoints.phase2 import normalize_statute_name_sample, extract_section_info_sample
        
        # Test statute name normalization
        test_cases = [
            ("The Apprenticeship Act 2018", "Apprenticeship Act 2018"),
            ("An Act to make provisions", "Act To Make Provisions"),  # Fixed: "to" should be capitalized
            ("Regulation No. 123", "Regulation No. 123"),
            ("   Multiple   Spaces   ", "Multiple Spaces"),
            ("", "UNKNOWN"),
            (None, "UNKNOWN"),
            (123, "123"),
        ]
        
        for input_name, expected in test_cases:
            result = normalize_statute_name_sample(input_name)
            # Check if the result is a dictionary (enhanced format) or string (old format)
            if isinstance(result, dict):
                normalized = result.get("normalized_result", "UNKNOWN")
                success = result.get("success", False)
                reason = result.get("reason", "No reason provided")
                processing_steps = result.get("processing_steps", [])
                
                if normalized == expected:
                    print(f"✅ '{input_name}' -> '{normalized}' (expected: '{expected}')")
                    print(f"   Success: {success}, Reason: {reason}")
                    print(f"   Processing steps: {len(processing_steps)} steps")
                else:
                    print(f"❌ '{input_name}' -> '{normalized}' (expected: '{expected}')")
                    print(f"   Success: {success}, Reason: {reason}")
                    print(f"   Processing steps: {len(processing_steps)} steps")
                    return False
            else:
                # Handle old string format for backward compatibility
                if result == expected:
                    print(f"✅ '{input_name}' -> '{result}' (expected: '{expected}')")
                else:
                    print(f"❌ '{input_name}' -> '{result}' (expected: '{expected}')")
                    return False
        
        # Test section extraction
        section_test_cases = [
            ("9. Counseling and placement service", "9", "Counseling and placement service"),
            ("Section 15", "15", ""),
            ("123", "123", ""),  # Fixed: "123" is correctly identified as a section number
            ("No section info", "", "No section info"),
            ("", "", ""),
            (None, "", ""),
        ]
        
        for input_text, expected_number, expected_definition in section_test_cases:
            result = extract_section_info_sample(input_text)
            # Check if the result is a dictionary (enhanced format) or old format
            if isinstance(result, dict):
                section_number = result.get("section_number", "")
                definition = result.get("definition", "")
                success = result.get("success", False)
                reason = result.get("reason", "No reason provided")
                confidence = result.get("confidence", "none")
                
                if section_number == expected_number and definition == expected_definition:
                    print(f"✅ Section '{input_text}' -> number: '{section_number}', definition: '{definition}'")
                    print(f"   Success: {success}, Reason: {reason}, Confidence: {confidence}")
                else:
                    print(f"❌ Section '{input_text}' -> number: '{section_number}', definition: '{definition}' (expected: '{expected_number}', '{expected_definition}')")
                    print(f"   Success: {success}, Reason: {reason}, Confidence: {confidence}")
                    return False
            else:
                # Handle old format for backward compatibility
                if result["section_number"] == expected_number and result["definition"] == expected_definition:
                    print(f"✅ Section '{input_text}' -> number: '{result['section_number']}', definition: '{result['definition']}'")
                else:
                    print(f"❌ Section '{input_text}' -> number: '{result['section_number']}', definition: '{result['definition']}' (expected: '{expected_number}', '{expected_definition}')")
                    return False
        
        print("✅ Normalization functions working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Normalization functions test failed: {e}")
        return False

def test_field_mapping():
    """Test the field mapping logic"""
    print("🧪 Testing field mapping logic...")
    
    try:
        from app.api.v1.endpoints.phase2 import FIELD_NAMES
        
        # Check that we have both source and normalized field mappings
        source_fields = [k for k in FIELD_NAMES.keys() if k.isupper()]
        normalized_fields = [k for k in FIELD_NAMES.keys() if k.islower()]
        
        print(f"📊 Found {len(source_fields)} source fields: {source_fields}")
        print(f"📊 Found {len(normalized_fields)} normalized fields: {normalized_fields}")
        
        # Check for key mappings
        key_mappings = [
            ("STATUTE_NAME", "statute_name"),
            ("ACT_ORDINANCE", "act_ordinance"),
            ("SECTION", "section_number"),
        ]
        
        for source_key, norm_key in key_mappings:
            if source_key in FIELD_NAMES and norm_key in FIELD_NAMES:
                print(f"✅ Mapping found: {source_key} -> {norm_key}")
            else:
                print(f"❌ Missing mapping: {source_key} -> {norm_key}")
                return False
        
        print("✅ Field mapping working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Field mapping test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting normalization logic tests...")
    print("=" * 50)
    
    tests = [
        test_field_name_constants,
        test_normalization_functions,
        test_field_mapping,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The normalization logic fix is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
