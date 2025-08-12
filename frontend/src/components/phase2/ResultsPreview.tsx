import React, { useState, useEffect, useCallback } from 'react';
import { Eye, RefreshCw, Download, AlertTriangle, CheckCircle, ChevronDown, ChevronRight, FileText, Hash, Text, Search, Filter } from 'lucide-react';

interface StatuteGroup {
  _id: string;
  Statute_Name: string;
  Sections: any[];
  section_count: number;
}

interface ResultsPreviewProps {
  config: any;
}

const ResultsPreview: React.FC<ResultsPreviewProps> = ({ config }) => {
  const [statuteGroups, setStatuteGroups] = useState<StatuteGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'preamble' | 'numeric' | 'text'>('all');
  const [sortOrder, setSortOrder] = useState<'name' | 'sections' | 'type'>('name');

  // Fetch statute groups from normalized collection
  const fetchResultsData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/phase2/preview-normalized-structure?limit=1000', {
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
        setMessage({ type: 'error', text: 'Failed to fetch results data' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Error fetching results data' });
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

  // Get section type
  const getSectionType = (section: any) => {
    const [sortType] = sectionSortKey(section);
    if (sortType === 0) return 'preamble';
    if (sortType === 1) return 'numeric';
    return 'text';
  };

  // Filter and sort statutes
  const getFilteredAndSortedStatutes = () => {
    let filtered = statuteGroups.filter(statute =>
      statute.Statute_Name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // Apply type filter
    if (filterType !== 'all') {
      filtered = filtered.filter(statute => {
        return statute.Sections.some((section: any) => getSectionType(section) === filterType);
      });
    }

    // Apply sorting
    filtered.sort((a, b) => {
      switch (sortOrder) {
        case 'name':
          return a.Statute_Name.localeCompare(b.Statute_Name);
        case 'sections':
          return b.section_count - a.section_count;
        case 'type':
          const aHasPreamble = a.Sections.some((section: any) => getSectionType(section) === 'preamble');
          const bHasPreamble = b.Sections.some((section: any) => getSectionType(section) === 'preamble');
          if (aHasPreamble && !bHasPreamble) return -1;
          if (!aHasPreamble && bHasPreamble) return 1;
          return a.Statute_Name.localeCompare(b.Statute_Name);
        default:
          return 0;
      }
    });

    return filtered;
  };

  // Export results
  const exportResults = async () => {
    try {
      const exportData = {
        export_date: new Date().toISOString(),
        total_statutes: statuteGroups.length,
        total_sections: statuteGroups.reduce((sum, statute) => sum + statute.section_count, 0),
        statutes: statuteGroups.map(statute => ({
          statute_name: statute.Statute_Name,
          section_count: statute.section_count,
          sections: statute.Sections.map((section: any) => ({
            number: section.number || section.section_number || 'N/A',
            type: getSectionType(section),
            content: section.definition || section.content || 'No content'
          }))
        }))
      };

      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `normalization_results_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setMessage({ type: 'success', text: 'Results exported successfully' });
    } catch (error) {
      setMessage({ type: 'error', text: 'Error exporting results' });
    }
  };

  useEffect(() => {
    fetchResultsData();
  }, [fetchResultsData]);

  const filteredStatutes = getFilteredAndSortedStatutes();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <Eye className="w-5 h-5 mr-2" />
          Results Preview - Grouped Structure
        </h2>
        <p className="text-gray-600 mb-4">
          Preview the final normalized results showing statutes grouped with their sorted sections.
        </p>
        
        {/* Controls */}
        <div className="flex flex-wrap gap-4 items-center">
          <button
            onClick={fetchResultsData}
            disabled={loading}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh Results
          </button>
          
          <button
            onClick={exportResults}
            disabled={statuteGroups.length === 0}
            className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center"
          >
            <Download className="w-4 h-4 mr-2" />
            Export Results
          </button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Search & Filters</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Search */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Search Statutes</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                placeholder="Search statute names..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Type Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Filter by Section Type</label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value as any)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="all">All Types</option>
              <option value="preamble">Has Preamble</option>
              <option value="numeric">Has Numeric Sections</option>
              <option value="text">Has Text Sections</option>
            </select>
          </div>

          {/* Sort Order */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Sort Order</label>
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as any)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="name">By Name (A-Z)</option>
              <option value="sections">By Section Count</option>
              <option value="type">By Type (Preamble First)</option>
            </select>
          </div>
        </div>

        {/* Results Summary */}
        <div className="mt-4 p-4 bg-gray-50 rounded-lg">
          <div className="text-sm text-gray-600">
            Showing {filteredStatutes.length} of {statuteGroups.length} statutes • 
            Total sections: {filteredStatutes.reduce((sum, statute) => sum + statute.section_count, 0)} • 
            Filter: {filterType === 'all' ? 'All types' : filterType} • 
            Sort: {sortOrder === 'name' ? 'By name' : sortOrder === 'sections' ? 'By section count' : 'By type'}
          </div>
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

      {/* Results Display */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Normalized Results</h3>
          <p className="text-sm text-gray-600">
            {filteredStatutes.length} statutes found • Click to expand and view sections
          </p>
        </div>
        
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
            Loading results...
          </div>
        ) : filteredStatutes.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            {searchTerm || filterType !== 'all' ? 'No statutes match your search/filter criteria.' : 'No results found. Run normalization first to populate the database.'}
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {filteredStatutes.map((statute) => (
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
                  
                  <div className="flex items-center space-x-4 text-sm text-gray-500">
                    <div className="flex items-center space-x-2">
                      {statute.Sections.some((section: any) => getSectionType(section) === 'preamble') && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          <FileText className="w-3 h-3 mr-1" />
                          Preamble
                        </span>
                      )}
                      {statute.Sections.some((section: any) => getSectionType(section) === 'numeric') && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          <Hash className="w-3 h-3 mr-1" />
                          Numeric
                        </span>
                      )}
                      {statute.Sections.some((section: any) => getSectionType(section) === 'text') && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          <Text className="w-3 h-3 mr-1" />
                          Text
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                
                {/* Expanded Sections View */}
                {expandedGroups.has(statute._id) && (
                  <div className="mt-3 ml-8 space-y-2">
                    <div className="text-sm text-gray-600 font-medium">Sorted Sections:</div>
                    {statute.Sections && statute.Sections.length > 0 ? (
                      <div className="space-y-2">
                        {statute.Sections.map((section: any, index: number) => {
                          const sectionType = getSectionType(section);
                          return (
                            <div key={index} className={`p-3 rounded-lg border-l-4 ${
                              sectionType === 'preamble' ? 'border-l-blue-500 bg-blue-50' :
                              sectionType === 'numeric' ? 'border-l-green-500 bg-green-50' :
                              'border-l-gray-500 bg-gray-50'
                            }`}>
                              <div className="flex items-center justify-between mb-2">
                                <div className="font-medium text-gray-700">
                                  {section.number || section.section_number || `Section ${index + 1}`}
                                </div>
                                <span className={`px-2 py-1 rounded text-xs font-medium ${
                                  sectionType === 'preamble' ? 'bg-blue-100 text-blue-800' :
                                  sectionType === 'numeric' ? 'bg-green-100 text-green-800' :
                                  'bg-gray-100 text-gray-800'
                                }`}>
                                  {sectionType === 'preamble' ? <FileText className="w-3 h-3 inline mr-1" /> :
                                   sectionType === 'numeric' ? <Hash className="w-3 h-3 inline mr-1" /> :
                                   <Text className="w-3 h-3 inline mr-1" />}
                                  {sectionType}
                                </span>
                              </div>
                              <div className="text-sm text-gray-600">
                                {section.definition || section.content || 'No content available'}
                              </div>
                              {section.year && (
                                <div className="text-xs text-gray-500 mt-1">
                                  Year: {section.year}
                                </div>
                              )}
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

      {/* Data Structure Info */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Data Structure Information</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-gray-900 mb-2">Output Schema</h4>
            <div className="bg-gray-50 p-3 rounded text-sm font-mono">
              <div>{"{"}</div>
              <div className="ml-4">"Statute_Name": "string",</div>
              <div className="ml-4">"Sections": [</div>
              <div className="ml-8">{"{"}</div>
              <div className="ml-12">"number": "string",</div>
              <div className="ml-12">"definition": "string",</div>
              <div className="ml-12">"year": "number",</div>
              <div className="ml-8">{"}"}</div>
              <div className="ml-4">]</div>
              <div>{"}"}</div>
            </div>
          </div>
          
          <div>
            <h4 className="font-medium text-gray-900 mb-2">Section Types</h4>
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 bg-blue-500 rounded"></div>
                <span className="text-sm text-gray-700">Preamble - Always sorted first</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 bg-green-500 rounded"></div>
                <span className="text-sm text-gray-700">Numeric - Sorted by value</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 bg-gray-500 rounded"></div>
                <span className="text-sm text-gray-700">Text - Sorted alphabetically</span>
              </div>
            </div>
            
            <div className="mt-4 p-3 bg-blue-50 rounded text-sm text-blue-800">
              <strong>Note:</strong> Each statute is now a single document containing all its sections, 
              making it easier to work with related legal content as a cohesive unit.
            </div>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="text-sm text-gray-600">
          Total: {statuteGroups.length} statute group(s) • 
          Total sections: {statuteGroups.reduce((sum, statute) => sum + statute.section_count, 0)} • 
          Showing: {filteredStatutes.length} filtered • 
          Data structure: Grouped with sorted sections
        </div>
      </div>
    </div>
  );
};

export default ResultsPreview;
