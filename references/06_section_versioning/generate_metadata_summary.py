"""
Generate Metadata Summary for Section Versioning

This script generates comprehensive metadata summaries for the section versioning process,
including statistics on versioning decisions, similarity distributions, and processing metrics.

Features:
- Aggregates metadata from multiple batch collections
- Calculates versioning statistics and distributions
- Generates similarity analysis reports
- Creates processing performance metrics
- Exports summary reports in multiple formats
- Provides insights into versioning quality
"""

import numpy as np
from pymongo import MongoClient
from tqdm import tqdm
import json
from datetime import datetime, date
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Any
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"
SOURCE_DB = "Consolidated-Statutes"  # Updated to match coherent pipeline
SOURCE_COLL = "statute"
JSON_FILE = "06_section_versioning/exports/all_section_versions.json"

# Initialize metadata tracking
metadata = {
    "total_statutes_analyzed": 0,
    "total_sections_analyzed": 0,
    "total_versions_analyzed": 0,
    "analysis_stats": {
        "unique_statutes": 0,
        "unique_sections": 0,
        "unique_versions": 0,
        "deduplication_rates": {
            "statutes": 0.0,
            "sections": 0.0,
            "versions": 0.0
        }
    },
    "content_breakdown": {
        "statute_repetitions": Counter(),
        "section_repetitions": Counter(),
        "version_repetitions": Counter(),
        "top_repeated_items": []
    },
    "processing_details": {
        "data_source": "database",
        "analysis_date": "",
        "processing_time": 0.0
    }
}

def connect_to_mongodb():
    """Connect to MongoDB"""
    try:
        client = MongoClient(MONGO_URI)
        client.admin.command('ping')
        print("✅ Connected to MongoDB successfully")
        return client
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return None

def load_data_from_database():
    """Load grouped statute data from database"""
    client = connect_to_mongodb()
    if not client:
        return []
    
    try:
        col = client[SOURCE_DB][SOURCE_COLL]
        data = list(col.find({}))
        print(f"📄 Loaded {len(data)} statutes from database")
        return data
    except Exception as e:
        print(f"❌ Error loading from database: {e}")
        return []
    finally:
        client.close()

def load_data_from_json():
    """Load grouped statute data from JSON file"""
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"📄 Loaded {len(data)} statutes from JSON file")
        return data
    except Exception as e:
        print(f"❌ Error loading from JSON: {e}")
        return []

def analyze_statutes_and_sections(data: List[Dict]) -> Dict:
    """
    Analyze statutes and sections to generate metadata summary
    Based on the grouping logic from statute and section versioning scripts
    
    Args:
        data: List of grouped statute documents
        
    Returns:
        Dictionary with metadata summary
    """
    # Use numpy arrays for efficient data processing
    base_names = np.array([statute.get("Base_Statute_Name", "") for statute in data])
    provinces = np.array([statute.get("Province", "") for statute in data])
    statute_types = np.array([statute.get("Statute_Type", "") for statute in data])
    
    # Create unique statute identifiers using numpy operations
    statute_ids = np.char.add(
        np.char.add(base_names, " ("),
        np.char.add(provinces, ", "),
        np.char.add(statute_types, ")")
    )
    
    # Collect unique statutes using numpy
    unique_statutes = set(statute_ids)
    statute_repetitions = Counter(statute_ids)
    
    # Collect all unique sections and versions using numpy operations
    unique_sections = set()
    section_repetitions = Counter()
    unique_versions = set()
    version_repetitions = Counter()
    
    # Track original vs grouped statistics
    original_sections = 0
    original_versions = 0
    grouped_sections = 0
    grouped_versions = 0
    
    # Process sections and versions efficiently
    for statute in data:
        base_name = statute.get("Base_Statute_Name", "")
        province = statute.get("Province", "")
        statute_type = statute.get("Statute_Type", "")
        
        # Analyze sections (based on section_number grouping from assign_section_versions.py)
        for section in statute.get("Section_Versions", []):
            section_number = section.get("Section", "")
            definition = section.get("Definition", "")
            
            # Create unique section identifier (based on section_number + definition grouping)
            section_id = f"{base_name} - Section {section_number}: {definition}"
            unique_sections.add(section_id)
            section_repetitions[section_id] += 1
            grouped_sections += 1
            
            # Analyze versions (based on semantic similarity grouping)
            for version in section.get("Versions", []):
                version_id = version.get("Version_ID", "")
                status = version.get("Status", "")
                year = version.get("Year")
                promulgation_date = version.get("Promulgation_Date", "")
                
                # Create unique version identifier (based on semantic similarity from assign_section_versions.py)
                version_identifier = f"{base_name} - Section {section_number} - {status} ({year}) - {promulgation_date}"
                unique_versions.add(version_identifier)
                version_repetitions[version_identifier] += 1
                grouped_versions += 1
                
                # Track original versions (before grouping)
                original_versions += 1
        
        # Track original sections (before grouping)
        original_sections += len(statute.get("Section_Versions", []))
    
    # Calculate deduplication statistics
    deduplication_stats = {
        "original_sections": original_sections,
        "grouped_sections": grouped_sections,
        "original_versions": original_versions,
        "grouped_versions": grouped_versions,
        "sections_deduplication_rate": ((original_sections - grouped_sections) / original_sections * 100) if original_sections > 0 else 0,
        "versions_deduplication_rate": ((original_versions - grouped_versions) / original_versions * 100) if original_versions > 0 else 0
    }
    
    # Create repetition breakdowns
    statute_breakdown = [
        {
            "title": statute_id,
            "count": count
        }
        for statute_id, count in statute_repetitions.most_common()
    ]
    
    section_breakdown = [
        {
            "title": section_id,
            "count": count
        }
        for section_id, count in section_repetitions.most_common()
    ]
    
    version_breakdown = [
        {
            "title": version_id,
            "count": count
        }
        for version_id, count in version_repetitions.most_common()
    ]
    
    return {
        "metadata": {
            "total_statutes": len(data),
            "unique_statutes": len(unique_statutes),
            "total_sections": grouped_sections,
            "unique_sections": len(unique_sections),
            "total_versions": grouped_versions,
            "unique_versions": len(unique_versions),
            "analysis_date": datetime.now().isoformat()
        },
        "deduplication_stats": deduplication_stats,
        "statute_breakdown": statute_breakdown,
        "section_breakdown": section_breakdown,
        "version_breakdown": version_breakdown,
        "top_repeated_statutes": statute_breakdown[:10],
        "top_repeated_sections": section_breakdown[:10],
        "top_repeated_versions": version_breakdown[:10]
    }
    
    # Create repetition breakdowns
    statute_breakdown = [
        {
            "title": statute_id,
            "count": count
        }
        for statute_id, count in statute_repetitions.most_common()
    ]
    
    section_breakdown = [
        {
            "title": section_id,
            "count": count
        }
        for section_id, count in section_repetitions.most_common()
    ]
    
    version_breakdown = [
        {
            "title": version_id,
            "count": count
        }
        for version_id, count in version_repetitions.most_common()
    ]
    
    return {
        "metadata": {
            "total_statutes": len(data),
            "unique_statutes": len(unique_statutes),
            "total_sections": total_sections,
            "unique_sections": len(unique_sections),
            "total_versions": total_versions,
            "unique_versions": len(unique_versions),
            "analysis_date": datetime.now().isoformat()
        },
        "statute_breakdown": statute_breakdown,
        "section_breakdown": section_breakdown,
        "version_breakdown": version_breakdown,
        "top_repeated_statutes": statute_breakdown[:10],
        "top_repeated_sections": section_breakdown[:10],
        "top_repeated_versions": version_breakdown[:10]
    }

def calculate_versioning_statistics(metadata_list: List[Dict]) -> Dict[str, Any]:
    """
    Calculate comprehensive versioning statistics using numpy for faster operations.
    """
    if not metadata_list:
        return {}
    
    # Convert metadata to numpy arrays for faster calculations
    total_sections = np.array([meta.get("total_sections_processed", 0) for meta in metadata_list])
    total_versions = np.array([meta.get("total_section_versions_created", 0) for meta in metadata_list])
    groups_processed = np.array([meta.get("versioning_stats", {}).get("base_statutes_processed", 0) for meta in metadata_list])
    
    # Calculate statistics using numpy operations
    stats = {
        "total_sections_processed": int(np.sum(total_sections)),
        "total_versions_created": int(np.sum(total_versions)),
        "total_groups_processed": int(np.sum(groups_processed)),
        "average_sections_per_group": float(np.mean(total_sections / np.maximum(groups_processed, 1))),
        "average_versions_per_section": float(np.mean(total_versions / np.maximum(total_sections, 1))),
        "versioning_efficiency": float(np.mean(total_versions / np.maximum(total_sections, 1)) * 100),
        "processing_distribution": {
            "min_sections": int(np.min(total_sections)),
            "max_sections": int(np.max(total_sections)),
            "std_sections": float(np.std(total_sections)),
            "median_sections": float(np.median(total_sections))
        }
    }
    
    return stats

def aggregate_similarity_metrics(metadata_list: List[Dict]) -> Dict[str, Any]:
    """
    Aggregate similarity metrics across all batches using numpy for faster calculations.
    """
    if not metadata_list:
        return {}
    
    # Extract similarity data using numpy operations
    similarity_scores = []
    similarity_thresholds = []
    
    for meta in metadata_list:
        similarity_data = meta.get("similarity_analysis", {})
        if "similarity_scores" in similarity_data:
            similarity_scores.extend(similarity_data["similarity_scores"])
        if "threshold_used" in similarity_data:
            similarity_thresholds.append(similarity_data["threshold_used"])
    
    if not similarity_scores:
        return {}
    
    # Convert to numpy arrays for faster calculations
    scores_array = np.array(similarity_scores)
    thresholds_array = np.array(similarity_thresholds) if similarity_thresholds else np.array([])
    
    metrics = {
        "total_similarity_comparisons": len(scores_array),
        "average_similarity_score": float(np.mean(scores_array)),
        "median_similarity_score": float(np.median(scores_array)),
        "similarity_distribution": {
            "min_score": float(np.min(scores_array)),
            "max_score": float(np.max(scores_array)),
            "std_score": float(np.std(scores_array)),
            "percentiles": {
                "25th": float(np.percentile(scores_array, 25)),
                "50th": float(np.percentile(scores_array, 50)),
                "75th": float(np.percentile(scores_array, 75)),
                "90th": float(np.percentile(scores_array, 90)),
                "95th": float(np.percentile(scores_array, 95))
            }
        }
    }
    
    if len(thresholds_array) > 0:
        metrics["threshold_analysis"] = {
            "average_threshold": float(np.mean(thresholds_array)),
            "threshold_range": {
                "min": float(np.min(thresholds_array)),
                "max": float(np.max(thresholds_array))
            }
        }
    
    return metrics

def generate_final_schema():
    """Generate the final schema JSON file"""
    schema = {
        "schema_version": "1.0",
        "description": "Final schema for grouped statute documents with section versions",
        "created_date": datetime.now().isoformat(),
        "schema": {
            "type": "object",
            "properties": {
                "Base_Statute_Name": {
                    "type": "string",
                    "description": "The base name of the statute (e.g., 'Constitution of Pakistan')"
                },
                "Province": {
                    "type": "string",
                    "description": "The province or jurisdiction (e.g., 'Federal', 'Punjab')"
                },
                "Statute_Type": {
                    "type": "string",
                    "description": "The type of legal document (e.g., 'Constitution', 'Act', 'Ordinance')"
                },
                "Section_Versions": {
                    "type": "array",
                    "description": "Array of section versions within this statute",
                    "items": {
                        "type": "object",
                        "properties": {
                            "Section": {
                                "type": "string",
                                "description": "Section number or identifier (e.g., '6', 'Preamble')"
                            },
                            "Definition": {
                                "type": "string",
                                "description": "Brief description of the section (e.g., 'High Treason')"
                            },
                            "Versions": {
                                "type": "array",
                                "description": "Array of version timelines for this section",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "Version_ID": {
                                            "type": "string",
                                            "description": "Unique version identifier (e.g., 'v1', 'v2')"
                                        },
                                        "Year": {
                                            "type": "integer",
                                            "description": "Year of promulgation"
                                        },
                                        "Promulgation_Date": {
                                            "type": "string",
                                            "description": "Date of promulgation (e.g., '14-Aug-1973')"
                                        },
                                        "Status": {
                                            "type": "string",
                                            "description": "Version status (e.g., 'Original', 'Amendment')"
                                        },
                                        "Statute": {
                                            "type": "string",
                                            "description": "The actual legal text of this section version"
                                        },
                                        "isActive": {
                                            "type": "boolean",
                                            "description": "Whether this version is currently active (false if expired ordinance)"
                                        }
                                    },
                                    "required": ["Version_ID", "Status", "Statute", "isActive"]
                                }
                            }
                        },
                        "required": ["Section", "Definition", "Versions"]
                    }
                }
            },
            "required": ["Base_Statute_Name", "Province", "Statute_Type", "Section_Versions"]
        },
        "example": {
            "Base_Statute_Name": "Constitution of Pakistan",
            "Province": "Federal",
            "Statute_Type": "Constitution",
            "Section_Versions": [
                {
                    "Section": "6",
                    "Definition": "High Treason",
                    "Versions": [
                        {
                            "Version_ID": "v1",
                            "Year": 1973,
                            "Promulgation_Date": "14-Aug-1973",
                            "Status": "Original",
                            "Statute": "Section 6 of Constitution (Original)",
                            "isActive": False
                        },
                        {
                            "Version_ID": "v2",
                            "Year": 2009,
                            "Promulgation_Date": "31-Jul-2009",
                            "Status": "Amendment",
                            "Statute": "Section 6 of Constitution (18th Amendment)",
                            "isActive": True
                        }
                    ]
                }
            ]
        }
    }
    
    # Save schema to file
    with open("06_section_versioning/final_schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, default=str)
    
    print("💾 Final schema saved to final_schema.json")
    return schema

def print_comprehensive_metadata():
    """Print comprehensive metadata about the analysis process"""
    print(f"\n📊 COMPREHENSIVE ANALYSIS METADATA:")
    print("=" * 60)
    print(f"📋 Total statutes analyzed: {metadata['total_statutes_analyzed']}")
    print(f"📋 Total sections analyzed: {metadata['total_sections_analyzed']}")
    print(f"📋 Total versions analyzed: {metadata['total_versions_analyzed']}")
    
    print(f"\n📊 Analysis Statistics:")
    print(f"   - Unique statutes: {metadata['analysis_stats']['unique_statutes']}")
    print(f"   - Unique sections: {metadata['analysis_stats']['unique_sections']}")
    print(f"   - Unique versions: {metadata['analysis_stats']['unique_versions']}")
    
    print(f"\n📊 Deduplication Rates:")
    print(f"   - Statutes: {metadata['analysis_stats']['deduplication_rates']['statutes']:.1f}%")
    print(f"   - Sections: {metadata['analysis_stats']['deduplication_rates']['sections']:.1f}%")
    print(f"   - Versions: {metadata['analysis_stats']['deduplication_rates']['versions']:.1f}%")
    
    print(f"\n📊 Top Repeated Items:")
    for i, item in enumerate(metadata["content_breakdown"]["top_repeated_items"][:10]):
        print(f"   {i+1}. {item['title']}: {item['count']} times")
    
    print(f"\n📊 Processing Details:")
    print(f"   - Data source: {metadata['processing_details']['data_source']}")
    print(f"   - Analysis date: {metadata['processing_details']['analysis_date']}")
    print(f"   - Processing time: {metadata['processing_details']['processing_time']:.2f} seconds")

def save_metadata_to_file():
    """Save comprehensive metadata to JSON file"""
    import os
    
    # Create metadata folder if it doesn't exist
    os.makedirs("metadata", exist_ok=True)
    
    # Save comprehensive metadata
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    metadata_file = f"metadata/analysis_metadata_{timestamp}.json"
    
    # Convert Counter objects to regular dictionaries for JSON serialization
    metadata_for_json = {
        "total_statutes_analyzed": metadata["total_statutes_analyzed"],
        "total_sections_analyzed": metadata["total_sections_analyzed"],
        "total_versions_analyzed": metadata["total_versions_analyzed"],
        "analysis_stats": metadata["analysis_stats"],
        "content_breakdown": {
            "statute_repetitions": dict(metadata["content_breakdown"]["statute_repetitions"]),
            "section_repetitions": dict(metadata["content_breakdown"]["section_repetitions"]),
            "version_repetitions": dict(metadata["content_breakdown"]["version_repetitions"]),
            "top_repeated_items": metadata["content_breakdown"]["top_repeated_items"]
        },
        "processing_details": metadata["processing_details"]
    }
    
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata_for_json, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n📊 Metadata saved to: {metadata_file}")

def main():
    """Main function to generate metadata summary"""
    import time
    start_time = time.time()
    
    print("🚀 Starting Metadata Summary Generation")
    
    try:
        # Try to load from database first
        data = load_data_from_database()
        if data:
            metadata["processing_details"]["data_source"] = "database"
        else:
            # Fallback to JSON file
            data = load_data_from_json()
            metadata["processing_details"]["data_source"] = "json"
        
        if not data:
            print("❌ No data found to analyze")
            return
        
        # Update metadata
        metadata["total_statutes_analyzed"] = len(data)
        metadata["processing_details"]["analysis_date"] = datetime.now().isoformat()
        
        # Analyze the data
        analysis_result = analyze_statutes_and_sections(data)
        
        # Update metadata with analysis results
        metadata["analysis_stats"]["unique_statutes"] = analysis_result["metadata"]["unique_statutes"]
        metadata["analysis_stats"]["unique_sections"] = analysis_result["metadata"]["unique_sections"]
        metadata["analysis_stats"]["unique_versions"] = analysis_result["metadata"]["unique_versions"]
        
        # Calculate total sections and versions
        total_sections = 0
        total_versions = 0
        for statute in data:
            for section in statute.get("Section_Versions", []):
                total_sections += 1
                total_versions += len(section.get("Versions", []))
        
        metadata["total_sections_analyzed"] = total_sections
        metadata["total_versions_analyzed"] = total_versions
        
        # Calculate deduplication rates
        if metadata["total_statutes_analyzed"] > 0:
            metadata["analysis_stats"]["deduplication_rates"]["statutes"] = (
                (metadata["total_statutes_analyzed"] - metadata["analysis_stats"]["unique_statutes"]) / 
                metadata["total_statutes_analyzed"] * 100
            )
        
        if metadata["total_sections_analyzed"] > 0:
            metadata["analysis_stats"]["deduplication_rates"]["sections"] = (
                (metadata["total_sections_analyzed"] - metadata["analysis_stats"]["unique_sections"]) / 
                metadata["total_sections_analyzed"] * 100
            )
        
        if metadata["total_versions_analyzed"] > 0:
            metadata["analysis_stats"]["deduplication_rates"]["versions"] = (
                (metadata["total_versions_analyzed"] - metadata["analysis_stats"]["unique_versions"]) / 
                metadata["total_versions_analyzed"] * 100
            )
        
        # Store repetition breakdowns
        for item in analysis_result.get("statute_breakdown", []):
            metadata["content_breakdown"]["statute_repetitions"][item["title"]] = item["count"]
        
        for item in analysis_result.get("section_breakdown", []):
            metadata["content_breakdown"]["section_repetitions"][item["title"]] = item["count"]
        
        for item in analysis_result.get("version_breakdown", []):
            metadata["content_breakdown"]["version_repetitions"][item["title"]] = item["count"]
        
        # Store top repeated items
        metadata["content_breakdown"]["top_repeated_items"] = analysis_result.get("top_repeated_statutes", [])
        
        # Calculate processing time
        metadata["processing_details"]["processing_time"] = time.time() - start_time
        
        # Print comprehensive metadata
        print_comprehensive_metadata()
        
        # Save metadata to file
        save_metadata_to_file()
        
        # Generate final schema
        final_schema = generate_final_schema()
        
        # Save analysis results
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_filename = f"metadata_summary_{SOURCE_DB}_{SOURCE_COLL}_{date_str}.json"
        summary_path = f"06_section_versioning/final_output/{summary_filename}"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(analysis_result, f, indent=2, default=str)

        schema_filename = f"final_schema_{SOURCE_DB}_{SOURCE_COLL}_{date_str}.json"
        schema_path = f"06_section_versioning/final_output/{schema_filename}"
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(final_schema, f, indent=2, default=str)

        print(f"✅ Metadata summary generation completed!")
        print(f"📄 Results saved to final_output/ as {summary_filename} and {schema_filename}")
        
    except Exception as e:
        print(f"❌ Error during metadata summary generation: {e}")
        raise

if __name__ == "__main__":
    main() 