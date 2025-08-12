import React, { useState, useEffect, useCallback } from 'react';
import { Settings, RefreshCw, Play, Eye, Save, AlertTriangle, CheckCircle, ChevronDown, ChevronRight, Database, X, Plus } from 'lucide-react';

interface StatuteGroup {
  _id: string;
  Statute_Name: string;
  Sections: any[];
  section_count: number;
}

interface FieldMapping {
  source: string;
  target: string;
  enabled: boolean;
}

interface StructureCleanerProps {
  config: any;
}

const StructureCleaner: React.FC<StructureCleanerProps> = ({ config }) => {
  const [statuteGroups, setStatuteGroups] = useState<StatuteGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [fieldMappings, setFieldMappings] = useState<FieldMapping[]>([
    { source: 'number', target: 'section_number', enabled: true },
    { source: 'definition', target: 'section_content', enabled: true },
    { source: 'content', target: 'section_text', enabled: true },
    { source: 'year', target: 'section_year', enabled: true },
    { source: 'date', target: 'section_date', enabled: true }
  ]);

  // Fetch statute groups from normalized collection
  const fetchStatuteGroups = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/phase2/preview-normalized-structure?limit=100', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      const data = await response.json();
      
      if (data.success && data.preview_data) {
        // Transform the data to match our interface
        const groups = data.preview_data.map((statute: any) => ({
          _id: statute.Statute_Name,
          Statute_Name: statute.Statute_Name,
          Sections: statute.Sections || [],
          section_count: statute.Sections?.length || 0
        }));
        setStatuteGroups(groups);
      } else {
        setMessage({ type: 'error', text: 'Failed to fetch statute groups' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Error fetching statute groups' });
    } finally {
      setLoading(false);
    }
  }, []);

  // Toggle group expansion
  const toggleGroupExpansion = (groupId: string) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(groupId)) {
      newExpanded.delete(groupId);
    } else {
      newExpanded.add(groupId);
    }
    setExpandedGroups(newExpanded);
  };

  // Update field mapping
  const updateFieldMapping = (index: number, field: keyof FieldMapping, value: any) => {
    const newMappings = [...fieldMappings];
    newMappings[index] = { ...newMappings[index], [field]: value };
    setFieldMappings(newMappings);
  };

  // Add new field mapping
  const addFieldMapping = () => {
    setFieldMappings([...fieldMappings, { source: '', target: '', enabled: true }]);
  };

  // Remove field mapping
  const removeFieldMapping = (index: number) => {
    const newMappings = fieldMappings.filter((_, i) => i !== index);
    setFieldMappings(newMappings);
  };

  // Preview structure cleaning
  const previewCleaning = async () => {
    setCleaning(true);
    try {
      // For now, create a preview based on current field mappings
      const preview = {
        success: true,
        message: 'Structure cleaning preview generated',
        sample_changes: statuteGroups.slice(0, 3).map(statute => ({
          statute_name: statute.Statute_Name,
          original_sections: statute.Sections.slice(0, 2).map((section: any) => ({
            original: section,
            cleaned: fieldMappings.reduce((cleaned: any, mapping) => {
              if (mapping.enabled && section[mapping.source] !== undefined) {
                cleaned[mapping.target] = section[mapping.source];
              }
              return cleaned;
            }, {})
          }))
        }))
      };
      
      setPreviewData(preview);
      setMessage({ type: 'success', text: 'Preview generated successfully' });
    } catch (error) {
      setMessage({ type: 'error', text: 'Error generating preview' });
    } finally {
      setCleaning(false);
    }
  };

  // Execute structure cleaning
  const executeCleaning = async () => {
    setCleaning(true);
    try {
      // For now, show a message that this feature needs backend implementation
      setMessage({ 
        type: 'error', 
        text: 'Structure cleaning execution requires backend implementation for the new grouped schema' 
      });
      
      // TODO: Implement backend endpoint to clean structure in grouped format
      // This would need to:
      // 1. Apply field mappings to all sections in all statutes
      // 2. Clean and standardize field values
      // 3. Update the normalized_statutes collection
      // 4. Return summary of changes made
      
    } catch (error) {
      setMessage({ type: 'error', text: 'Error executing structure cleaning' });
    } finally {
      setCleaning(false);
    }
  };

  useEffect(() => {
    fetchStatuteGroups();
  }, [fetchStatuteGroups]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <Settings className="w-5 h-5 mr-2" />
          Structure Cleaner - Grouped Schema
        </h2>
        <p className="text-gray-600 mb-4">
          Clean and standardize the structure of sections within each statute group. 
          Map fields, clean values, and ensure consistency across all sections.
        </p>
        
        {/* Controls */}
        <div className="flex flex-wrap gap-4 items-center">
          <button
            onClick={fetchStatuteGroups}
            disabled={loading}
            className="bg-gray-600 text-white px-4 py-2 rounded-lg hover:bg-gray-700 disabled:opacity-50 flex items-center"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh Data
          </button>
          
          <button
            onClick={previewCleaning}
            disabled={cleaning || statuteGroups.length === 0}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center"
          >
            <Eye className="w-4 h-4 mr-2" />
            Preview Changes
          </button>
          
          <button
            onClick={executeCleaning}
            disabled={cleaning || statuteGroups.length === 0}
            className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center"
          >
            <Play className="w-4 h-4 mr-2" />
            Execute Cleaning
          </button>
        </div>
      </div>

      {/* Field Mappings */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Field Mappings</h3>
        <p className="text-gray-600 mb-4">
          Define how section fields should be mapped and cleaned. Each mapping transforms a source field to a target field.
        </p>
        
        <div className="space-y-3">
          {fieldMappings.map((mapping, index) => (
            <div key={index} className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
              <input
                type="checkbox"
                checked={mapping.enabled}
                onChange={(e) => updateFieldMapping(index, 'enabled', e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              
              <div className="flex-1 grid grid-cols-2 gap-3">
                <input
                  type="text"
                  placeholder="Source field"
                  value={mapping.source}
                  onChange={(e) => updateFieldMapping(index, 'source', e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
                />
                <input
                  type="text"
                  placeholder="Target field"
                  value={mapping.target}
                  onChange={(e) => updateFieldMapping(index, 'target', e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <button
                onClick={() => removeFieldMapping(index)}
                className="text-red-600 hover:text-red-800 p-1"
                title="Remove mapping"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
        
        <button
          onClick={addFieldMapping}
          className="mt-3 bg-blue-100 text-blue-700 px-4 py-2 rounded-lg hover:bg-blue-200 flex items-center"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Field Mapping
        </button>
      </div>

      {/* Message Display */}
      {message && (
        <div className={`p-4 rounded-lg flex items-center ${
          message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle className="w-5 h-5 mr-2" />
          ) : (
            <AlertTriangle className="w-5 h-5 mr-2" />
          )}
          {message.text}
        </div>
      )}

      {/* Preview Data */}
      {previewData && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Eye className="w-5 h-5 mr-2" />
            Cleaning Preview
          </h3>
          
          <div className="space-y-4">
            {previewData.sample_changes?.map((statute: any, index: number) => (
              <div key={index} className="border border-gray-200 rounded-lg p-4">
                <h4 className="font-medium text-gray-900 mb-3">{statute.statute_name}</h4>
                
                <div className="space-y-3">
                  {statute.original_sections?.map((section: any, sIndex: number) => (
                    <div key={sIndex} className="grid grid-cols-2 gap-4">
                      <div className="bg-gray-50 p-3 rounded">
                        <div className="text-sm font-medium text-gray-700 mb-2">Original</div>
                        <pre className="text-xs text-gray-600 overflow-auto">
                          {JSON.stringify(section.original, null, 2)}
                        </pre>
                      </div>
                      
                      <div className="bg-blue-50 p-3 rounded">
                        <div className="text-sm font-medium text-blue-700 mb-2">Cleaned</div>
                        <pre className="text-xs text-blue-600 overflow-auto">
                          {JSON.stringify(section.cleaned, null, 2)}
                        </pre>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Statute Groups List */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Statute Groups</h3>
          <p className="text-sm text-gray-600">
            {statuteGroups.length} groups loaded • Click to expand and view sections
          </p>
        </div>
        
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
            Loading statute groups...
          </div>
        ) : statuteGroups.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No statute groups found. Run normalization first to populate the database.
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {statuteGroups.map((statute) => (
              <div key={statute._id} className="p-4">
                <div className="flex items-center justify-between">
                  <button
                    onClick={() => toggleGroupExpansion(statute._id)}
                    className="flex items-center space-x-2 text-left hover:text-blue-600"
                  >
                    {expandedGroups.has(statute._id) ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                    <span className="font-medium text-gray-900">{statute.Statute_Name}</span>
                    <span className="text-sm text-gray-500">({statute.section_count} sections)</span>
                  </button>
                  
                  <div className="text-sm text-gray-500">
                    Fields: {statute.Sections.length > 0 ? Object.keys(statute.Sections[0]).join(', ') : 'None'}
                  </div>
                </div>
                
                {/* Expanded Sections View */}
                {expandedGroups.has(statute._id) && (
                  <div className="mt-3 ml-8 space-y-2">
                    <div className="text-sm text-gray-600 font-medium">Section Structure:</div>
                    {statute.Sections && statute.Sections.length > 0 ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                        {statute.Sections.slice(0, 6).map((section: any, index: number) => (
                          <div key={index} className="bg-gray-50 p-2 rounded text-sm">
                            <div className="font-medium text-gray-700 mb-1">
                              Section {index + 1}
                            </div>
                            <div className="text-xs text-gray-600">
                              {Object.keys(section).map(field => (
                                <div key={field} className="flex justify-between">
                                  <span>{field}:</span>
                                  <span className="truncate max-w-20">
                                    {typeof section[field] === 'string' && section[field].length > 20 
                                      ? `${section[field].substring(0, 20)}...` 
                                      : String(section[field] || '')}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                        {statute.Sections.length > 6 && (
                          <div className="bg-gray-100 p-2 rounded text-xs text-gray-500 text-center">
                            +{statute.Sections.length - 6} more sections
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-gray-500 text-sm">No sections found</div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Summary */}
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="text-sm text-gray-600">
          Total: {statuteGroups.length} statute group(s) • 
          Total sections: {statuteGroups.reduce((sum, statute) => sum + statute.section_count, 0)} • 
          Active mappings: {fieldMappings.filter(m => m.enabled).length}
        </div>
      </div>
    </div>
  );
};

export default StructureCleaner;
