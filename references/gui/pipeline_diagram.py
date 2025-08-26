#!/usr/bin/env python3
"""
LawChronicle Pipeline Flow Diagram Generator
Creates a visual flow diagram of the complete data processing pipeline
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ConnectionPatch
import numpy as np

# Set up the figure
fig, ax = plt.subplots(1, 1, figsize=(20, 16))
ax.set_xlim(0, 20)
ax.set_ylim(0, 16)
ax.axis('off')

# Colors for different phases
colors = {
    'ingestion': '#e1f5fe',
    'normalization': '#f3e5f5', 
    'cleaning': '#fff3e0',
    'dates': '#e8f5e8',
    'versioning': '#fce4ec',
    'sectioning': '#f1f8e9',
    'export': '#e0f2f1',
    'output': '#fff8e1'
}

# Define nodes with positions
nodes = {
    # Raw Data
    'raw_data': {'pos': (2, 15), 'text': '📄 Raw Statute Data\nStatute-Batch-1.statute.json', 'color': colors['output']},
    
    # Phase 1: Data Ingestion
    'phase1': {'pos': (2, 13.5), 'text': '01_data_ingestion', 'color': colors['ingestion']},
    'connect_db': {'pos': (2, 12.5), 'text': 'connect_existing_db.py\nConnect to existing database', 'color': colors['ingestion']},
    
    # Phase 2: Database Normalization
    'phase2': {'pos': (2, 11), 'text': '02_db_normalization', 'color': colors['normalization']},
    'create_db': {'pos': (2, 10), 'text': 'create_clean_db.py\nCreate clean database structure', 'color': colors['normalization']},
    'normalize': {'pos': (2, 8.5), 'text': 'normalize_structure.py\nNormalize data structure', 'color': colors['normalization']},
    
    # Phase 3: Field Cleaning & Splitting
    'phase3': {'pos': (2, 7), 'text': '03_field_cleaning_splitting', 'color': colors['cleaning']},
    'bring_fields': {'pos': (2, 6), 'text': 'bring_common_fields_up.py\nMove common fields to top level', 'color': colors['cleaning']},
    'drop_fields': {'pos': (2, 4.5), 'text': 'drop_unnecessary_fields.py\nRemove unnecessary fields', 'color': colors['cleaning']},
    'clean_sections': {'pos': (2, 3), 'text': 'cleaning_single_section.py\nClean individual sections', 'color': colors['cleaning']},
    'sort_sections': {'pos': (2, 1.5), 'text': 'sort_sections.py\nSort sections by number', 'color': colors['cleaning']},
    'remove_duplicates': {'pos': (2, 0), 'text': 'remove_preamble_duplicates_advanced.py\nRemove duplicate preambles', 'color': colors['cleaning']},
    'split_statutes': {'pos': (2, -1.5), 'text': 'split_cleaned_statute.py\nSplit cleaned statutes', 'color': colors['cleaning']},
    
    # Phase 4: Date Processing
    'phase4': {'pos': (6, 7), 'text': '04_date_processing', 'color': colors['dates']},
    'get_dates': {'pos': (6, 6), 'text': 'get_null_dates.py\nIdentify missing dates', 'color': colors['dates']},
    'search_dates': {'pos': (6, 4.5), 'text': 'search_dates.py\nSearch for dates in text', 'color': colors['dates']},
    'regex_dates': {'pos': (6, 3), 'text': 'search_dates_regex.py\nExtract dates with regex', 'color': colors['dates']},
    'parse_dates': {'pos': (6, 1.5), 'text': 'parse_dates.py\nParse and standardize dates', 'color': colors['dates']},
    'enrich_dates': {'pos': (6, 0), 'text': 'enrich_missing_dates.py\nFill missing dates', 'color': colors['dates']},
    
    # Phase 5: Statute Versioning
    'phase5': {'pos': (10, 7), 'text': '05_statute_versioning', 'color': colors['versioning']},
    'group_statutes': {'pos': (10, 6), 'text': 'group_statutes_by_base.py\nGroup statutes by base name', 'color': colors['versioning']},
    'assign_versions': {'pos': (10, 4.5), 'text': 'assign_statute_versions.py\nAssign version labels', 'color': colors['versioning']},
    'remove_dups': {'pos': (10, 3), 'text': 'remove_duplicates.py\nRemove duplicate statutes', 'color': colors['versioning']},
    
    # Phase 6: Section Versioning
    'phase6': {'pos': (14, 7), 'text': '06_section_versioning', 'color': colors['sectioning']},
    'split_sections': {'pos': (14, 6), 'text': 'split_sections.py\nExtract sections from statutes', 'color': colors['sectioning']},
    'assign_section_versions': {'pos': (14, 4.5), 'text': 'assign_section_versions.py\nAssign section versions', 'color': colors['sectioning']},
    'export_sections': {'pos': (14, 3), 'text': 'export_section_versions.py\nExport to JSON', 'color': colors['sectioning']},
    'consolidate': {'pos': (14, 1.5), 'text': 'create_consolidated_statutes.py\nCreate consolidated statutes', 'color': colors['sectioning']},
    'grouped_db': {'pos': (14, 0), 'text': 'create_grouped_statute_db.py\nCreate grouped statute DB', 'color': colors['sectioning']},
    'metadata_summary': {'pos': (14, -1.5), 'text': 'generate_metadata_summary.py\nGenerate metadata summary', 'color': colors['sectioning']},
    
    # Phase 7: Export Pipeline
    'phase7': {'pos': (18, 7), 'text': '07_export_pipeline', 'color': colors['export']},
    'export_json': {'pos': (18, 6), 'text': 'export_to_json.py\nExport to JSON format', 'color': colors['export']},
    'export_mongo': {'pos': (18, 4.5), 'text': 'export_to_mongo.py\nExport to MongoDB', 'color': colors['export']},
    
    # Output Files
    'json_exports': {'pos': (10, -3), 'text': '📄 JSON Exports\nall_section_versions.json', 'color': colors['output']},
    'consolidated_db': {'pos': (12, -3), 'text': '🗄️ Consolidated Database\nConsolidated-Statutes.statute', 'color': colors['output']},
    'grouped_db_out': {'pos': (14, -3), 'text': '🗄️ Grouped Database\nGrouped-Statute-Versions.statute', 'color': colors['output']},
    'metadata_files': {'pos': (16, -3), 'text': '📊 Metadata Files\nmetadata/ folder', 'color': colors['output']},
    'final_json': {'pos': (18, 3), 'text': '📄 Final JSON Exports', 'color': colors['output']},
    'final_mongo': {'pos': (18, 1.5), 'text': '🗄️ Final MongoDB Exports', 'color': colors['output']}
}

# Draw nodes
for node_name, node_data in nodes.items():
    x, y = node_data['pos']
    color = node_data['color']
    text = node_data['text']
    
    # Create rounded rectangle
    if 'phase' in node_name:
        # Phase headers are larger
        rect = FancyBboxPatch((x-1.5, y-0.5), 3, 1, 
                             boxstyle="round,pad=0.1", 
                             facecolor=color, edgecolor='black', linewidth=2)
    else:
        # Regular nodes
        rect = FancyBboxPatch((x-1.2, y-0.4), 2.4, 0.8, 
                             boxstyle="round,pad=0.05", 
                             facecolor=color, edgecolor='black', linewidth=1)
    
    ax.add_patch(rect)
    
    # Add text
    ax.text(x, y, text, ha='center', va='center', fontsize=8, 
            weight='bold' if 'phase' in node_name else 'normal')

# Define connections
connections = [
    # Main flow
    ('raw_data', 'phase1'),
    ('phase1', 'connect_db'),
    ('connect_db', 'phase2'),
    ('phase2', 'create_db'),
    ('create_db', 'normalize'),
    ('normalize', 'phase3'),
    ('phase3', 'bring_fields'),
    ('bring_fields', 'drop_fields'),
    ('drop_fields', 'clean_sections'),
    ('clean_sections', 'sort_sections'),
    ('sort_sections', 'remove_duplicates'),
    ('remove_duplicates', 'split_statutes'),
    
    # Date processing parallel
    ('split_statutes', 'phase4'),
    ('phase4', 'get_dates'),
    ('get_dates', 'search_dates'),
    ('search_dates', 'regex_dates'),
    ('regex_dates', 'parse_dates'),
    ('parse_dates', 'enrich_dates'),
    
    # Statute versioning
    ('enrich_dates', 'phase5'),
    ('phase5', 'group_statutes'),
    ('group_statutes', 'assign_versions'),
    ('assign_versions', 'remove_dups'),
    
    # Section versioning
    ('remove_dups', 'phase6'),
    ('phase6', 'split_sections'),
    ('split_sections', 'assign_section_versions'),
    ('assign_section_versions', 'export_sections'),
    ('assign_section_versions', 'consolidate'),
    ('assign_section_versions', 'grouped_db'),
    ('export_sections', 'metadata_summary'),
    ('consolidate', 'metadata_summary'),
    ('grouped_db', 'metadata_summary'),
    
    # Export pipeline
    ('metadata_summary', 'phase7'),
    ('phase7', 'export_json'),
    ('phase7', 'export_mongo'),
    
    # Output connections
    ('export_sections', 'json_exports'),
    ('consolidate', 'consolidated_db'),
    ('grouped_db', 'grouped_db_out'),
    ('metadata_summary', 'metadata_files'),
    ('export_json', 'final_json'),
    ('export_mongo', 'final_mongo')
]

# Draw connections
for start_node, end_node in connections:
    start_pos = nodes[start_node]['pos']
    end_pos = nodes[end_node]['pos']
    
    # Create arrow
    arrow = ConnectionPatch(start_pos, end_pos, "data", "data",
                          arrowstyle="->", shrinkA=5, shrinkB=5,
                          mutation_scale=20, fc="black", ec="black", linewidth=1.5)
    ax.add_patch(arrow)

# Add title
ax.text(10, 15.5, '🏛️ LawChronicle Complete Data Processing Pipeline', 
        ha='center', va='center', fontsize=16, weight='bold')

# Add legend
legend_elements = [
    patches.Patch(color=colors['ingestion'], label='Data Ingestion'),
    patches.Patch(color=colors['normalization'], label='Database Normalization'),
    patches.Patch(color=colors['cleaning'], label='Field Cleaning & Splitting'),
    patches.Patch(color=colors['dates'], label='Date Processing'),
    patches.Patch(color=colors['versioning'], label='Statute Versioning'),
    patches.Patch(color=colors['sectioning'], label='Section Versioning'),
    patches.Patch(color=colors['export'], label='Export Pipeline'),
    patches.Patch(color=colors['output'], label='Output Files')
]

ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(0.98, 0.98))

# Add parallel processing note
ax.text(10, -4.5, '⚡ Parallel Processing: export_section_versions.py and create_consolidated_statutes.py can run simultaneously', 
        ha='center', va='center', fontsize=10, style='italic', color='blue')

plt.tight_layout()
plt.savefig('lawchronicle_pipeline_diagram.png', dpi=300, bbox_inches='tight')
plt.savefig('lawchronicle_pipeline_diagram.pdf', bbox_inches='tight')
print("✅ Diagram saved as 'lawchronicle_pipeline_diagram.png' and 'lawchronicle_pipeline_diagram.pdf'")
plt.show() 