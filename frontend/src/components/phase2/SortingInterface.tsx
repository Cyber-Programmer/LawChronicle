import React, { useState, useEffect, useCallback } from 'react';
import { SortAsc, RefreshCw, Play, Eye, AlertTriangle, CheckCircle, ChevronDown, ChevronRight, ArrowUpDown, Hash, Text, FileText } from 'lucide-react';

interface StatuteGroup {
  _id: string;
  Statute_Name: string;
  Sections: any[];
  section_count: number;
}

interface SortingInterfaceProps {
  config: any;
}

const SortingInterface: React.FC<SortingInterfaceProps> = ({ config }) => {
  const [statuteGroups, setStatuteGroups] = useState<StatuteGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [sorting, setSorting] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [sortOptions, setSortOptions] = useState({
    preambleFirst: true,
    numericOrder: true,
    alphabeticalFallback: true,
    customSortOrder: false
  });

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

  // Section sort key function (replicating backend logic)
  const sectionSortKey = (section: any) => {
    const num = section.number || section.section_number || "";
    
    // Preamble always first
    if (typeof num === 'string' && num.trim().toLowerCase() === 'preamble') {
      return [0, ''];
    }
    
    // Try to parse as numeric
    try {
      const numStr = String(num).trim();
      if (numStr.replace(/[.-]/g, '').match(/^\d+$/)) {
        return [1, parseFloat(numStr)];
      }
    } catch (e) {
      // Ignore parsing errors
    }
    
    // Non-numeric sections last, sorted alphabetically
    return [2, String(num).toLowerCase()];
  };

  // Preview sorting changes
  const previewSorting = async () => {
    setSorting(true);
    try {
      // Create a preview showing how sections would be sorted
      const preview = {
        success: true,
        message: 'Sorting preview generated',
        sample_changes: statuteGroups.slice(0, 5).map(statute => {
          const originalSections = [...statute.Sections];
          const sortedSections = [...statute.Sections].sort((a, b) => {
            const [aType, aValue] = sectionSortKey(a);
            const [bType, bValue] = sectionSortKey(b);
            
            if (aType !== bType) return (aType as number) - (bType as number);
            if (aType === 1) return (aValue as number) - (bValue as number); // Numeric comparison
            return String(aValue).localeCompare(String(bValue)); // String comparison
          });
          
          return {
            statute_name: statute.Statute_Name,
            original_order: originalSections.slice(0, 3).map((section: any, index: number) => ({
              position: index + 1,
              number: section.number || section.section_number || `Section ${index + 1}`,
              type: sectionSortKey(section)[0] === 0 ? 'preamble' : 
                    sectionSortKey(section)[0] === 1 ? 'numeric' : 'text'
            })),
            sorted_order: sortedSections.slice(0, 3).map((section: any, index: number) => ({
              position: index + 1,
              number: section.number || section.section_number || `Section ${index + 1}`,
              type: sectionSortKey(section)[0] === 0 ? 'preamble' : 
                    sectionSortKey(section)[0] === 1 ? 'numeric' : 'text'
            }))
          };
        })
      };
      
      setPreviewData(preview);
      setMessage({ type: 'success', text: 'Sorting preview generated successfully' });
    } catch (error) {
      setMessage({ type: 'error', text: 'Error generating sorting preview' });
    } finally {
      setSorting(false);
    }
  };

  // Execute sorting
  const executeSorting = async () => {
    setSorting(true);
    try {
      // For now, show a message that this feature needs backend implementation
      setMessage({ 
        type: 'error', 
        text: 'Sorting execution requires backend implementation for the new grouped schema' 
      });
      
      // TODO: Implement backend endpoint to re-sort sections in grouped format
      // This would need to:
      // 1. Apply the section sort key to all sections in all statutes
      // 2. Update the normalized_statutes collection with re-sorted sections
      // 3. Return summary of sorting changes made
      
    } catch (error) {
      setMessage({ type: 'error', text: 'Error executing sorting' });
    } finally {
      setSorting(false);
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
          <SortAsc className="w-5 h-5 mr-2" />
          Sorting Interface - Grouped Sections
        </h2>
        <p className="text-gray-600 mb-4">
          Configure and preview how sections within each statute group should be sorted. 
          Default sorting: preamble first, then numeric sections, then text sections.
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
            onClick={previewSorting}
            disabled={sorting || statuteGroups.length === 0}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center"
          >
            <Eye className="w-4 h-4 mr-2" />
            Preview Sorting
          </button>
          
          <button
            onClick={executeSorting}
            disabled={sorting || statuteGroups.length === 0}
            className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center"
          >
            <Play className="w-4 h-4 mr-2" />
            Execute Sorting
          </button>
        </div>
      </div>

      {/* Sorting Options */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Sorting Configuration</h3>
        <p className="text-gray-600 mb-4">
          Configure the sorting behavior for sections within each statute group.
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex items-center space-x-3">
            <input
              type="checkbox"
              checked={sortOptions.preambleFirst}
              onChange={(e) => setSortOptions(prev => ({ ...prev, preambleFirst: e.target.checked }))}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <div>
              <div className="font-medium text-gray-900">Preamble First</div>
              <div className="text-sm text-gray-600">Always place preamble sections at the beginning</div>
            </div>
          </label>
          
          <label className="flex items-center space-x-3">
            <input
              type="checkbox"
              checked={sortOptions.numericOrder}
              onChange={(e) => setSortOptions(prev => ({ ...prev, numericOrder: e.target.checked }))}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <div>
              <div className="font-medium text-gray-900">Numeric Order</div>
              <div className="text-sm text-gray-600">Sort numeric sections in ascending order</div>
            </div>
          </label>
          
          <label className="flex items-center space-x-3">
            <input
              type="checkbox"
              checked={sortOptions.alphabeticalFallback}
              onChange={(e) => setSortOptions(prev => ({ ...prev, alphabeticalFallback: e.target.checked }))}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <div>
              <div className="font-medium text-gray-900">Alphabetical Fallback</div>
              <div className="text-sm text-gray-600">Sort non-numeric sections alphabetically</div>
            </div>
          </label>
          
          <label className="flex items-center space-x-3">
            <input
              type="checkbox"
              checked={sortOptions.customSortOrder}
              onChange={(e) => setSortOptions(prev => ({ ...prev, customSortOrder: e.target.checked }))}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <div>
              <div className="font-medium text-gray-900">Custom Sort Order</div>
              <div className="text-sm text-gray-600">Enable custom sorting rules (advanced)</div>
            </div>
          </label>
        </div>
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
            Sorting Preview
          </h3>
          
          <div className="space-y-4">
            {previewData.sample_changes?.map((statute: any, index: number) => (
              <div key={index} className="border border-gray-200 rounded-lg p-4">
                <h4 className="font-medium text-gray-900 mb-3">{statute.statute_name}</h4>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-gray-50 p-3 rounded">
                    <div className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                      <ArrowUpDown className="w-4 h-4 mr-1" />
                      Original Order
                    </div>
                    <div className="space-y-1">
                      {statute.original_order?.map((section: any, sIndex: number) => (
                        <div key={sIndex} className="flex items-center space-x-2 text-sm">
                          <span className="text-gray-500">{section.position}.</span>
                          <span className="font-medium">{section.number}</span>
                          <span className={`px-2 py-1 rounded text-xs ${
                            section.type === 'preamble' ? 'bg-blue-100 text-blue-800' :
                            section.type === 'numeric' ? 'bg-green-100 text-green-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {section.type === 'preamble' ? <FileText className="w-3 h-3 inline mr-1" /> :
                             section.type === 'numeric' ? <Hash className="w-3 h-3 inline mr-1" /> :
                             <Text className="w-3 h-3 inline mr-1" />}
                            {section.type}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div className="bg-blue-50 p-3 rounded">
                    <div className="text-sm font-medium text-blue-700 mb-2 flex items-center">
                      <SortAsc className="w-4 h-4 mr-1" />
                      Sorted Order
                    </div>
                    <div className="space-y-1">
                      {statute.sorted_order?.map((section: any, sIndex: number) => (
                        <div key={sIndex} className="flex items-center space-x-2 text-sm">
                          <span className="text-blue-500">{section.position}.</span>
                          <span className="font-medium">{section.number}</span>
                          <span className={`px-2 py-1 rounded text-xs ${
                            section.type === 'preamble' ? 'bg-blue-100 text-blue-800' :
                            section.type === 'numeric' ? 'bg-green-100 text-green-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {section.type === 'preamble' ? <FileText className="w-3 h-3 inline mr-1" /> :
                             section.type === 'numeric' ? <Hash className="w-3 h-3 inline mr-1" /> :
                             <Text className="w-3 h-3 inline mr-1" />}
                            {section.type}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
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
            {statuteGroups.length} groups loaded • Click to expand and view current section order
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
                    Current order: {statute.Sections.length > 0 ? 
                      `${statute.Sections[0].number || 'N/A'} → ${statute.Sections[statute.Sections.length - 1]?.number || 'N/A'}` : 
                      'No sections'}
                  </div>
                </div>
                
                {/* Expanded Sections View */}
                {expandedGroups.has(statute._id) && (
                  <div className="mt-3 ml-8 space-y-2">
                    <div className="text-sm text-gray-600 font-medium">Current Section Order:</div>
                    {statute.Sections && statute.Sections.length > 0 ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                        {statute.Sections.map((section: any, index: number) => {
                          const [sortType] = sectionSortKey(section);
                          const sectionType = sortType === 0 ? 'preamble' : sortType === 1 ? 'numeric' : 'text';
                          
                          return (
                            <div key={index} className={`p-2 rounded text-sm border-l-4 ${
                              sectionType === 'preamble' ? 'border-l-blue-500 bg-blue-50' :
                              sectionType === 'numeric' ? 'border-l-green-500 bg-green-50' :
                              'border-l-gray-500 bg-gray-50'
                            }`}>
                              <div className="flex items-center justify-between">
                                <span className="font-medium text-gray-700">
                                  {section.number || section.section_number || `Section ${index + 1}`}
                                </span>
                                <span className={`px-2 py-1 rounded text-xs ${
                                  sectionType === 'preamble' ? 'bg-blue-100 text-blue-800' :
                                  sectionType === 'numeric' ? 'bg-green-100 text-green-800' :
                                  'bg-gray-100 text-gray-800'
                                }`}>
                                  {sectionType}
                                </span>
                              </div>
                              <div className="text-xs text-gray-600 mt-1 truncate">
                                {section.definition || section.content || 'No content'}
                              </div>
                            </div>
                          );
                        })}
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
          Sorting: {sortOptions.preambleFirst ? 'Preamble first' : 'No preamble priority'} • 
          {sortOptions.numericOrder ? 'Numeric order' : 'No numeric order'} • 
          {sortOptions.alphabeticalFallback ? 'Alphabetical fallback' : 'No alphabetical fallback'}
        </div>
      </div>
    </div>
  );
};

export default SortingInterface;
