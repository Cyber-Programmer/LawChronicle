import React, { useState, useEffect, useCallback } from 'react';
import { 
  Eye, RefreshCw, Download, AlertTriangle, CheckCircle, ChevronDown, ChevronRight, 
  FileText, Hash, Text, Search, SortAsc, Settings, BarChart3, History,
  Play, TrendingUp, Clock, Database, ArrowUpDown
} from 'lucide-react';
import FieldMappingEditor from './FieldMappingEditor';

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

interface ProgressMetrics {
  total_statutes: number;
  processed_statutes: number;
  total_sections: number;
  processed_sections: number;
  normalization_progress: number;
  sorting_progress: number;
  overall_progress: number;
  estimated_time_remaining: string;
  current_phase: string;
  last_updated: string;
}

interface ResultsPreviewProps {
  config: any;
}

const ResultsPreview: React.FC<ResultsPreviewProps> = ({ config }) => {
  // Core state
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(100);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // Page size options
  const pageSizeOptions = [25, 50, 100, 200, 500];
  const [statuteGroups, setStatuteGroups] = useState<StatuteGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'preamble' | 'numeric' | 'text'>('all');
  const [sortOrder, setSortOrder] = useState<'name' | 'sections' | 'type'>('name');

  // Sub-panel state
  const [expandedPanels, setExpandedPanels] = useState<Set<string>>(new Set(['main']));
  const [sortOptions, setSortOptions] = useState({
    preambleFirst: true,
    numericOrder: true,
    alphabeticalFallback: true,
    customSortOrder: false
  });
  const [fieldMappings, setFieldMappings] = useState<FieldMapping[]>([
    { source: 'number', target: 'section_number', enabled: true },
    { source: 'definition', target: 'section_content', enabled: true },
    { source: 'content', target: 'section_text', enabled: true },
    { source: 'year', target: 'section_year', enabled: true },
    { source: 'date', target: 'section_date', enabled: true }
  ]);
  const [progressMetrics, setProgressMetrics] = useState<ProgressMetrics | null>(null);

  // Fetch statute groups from normalized collection
  const fetchResultsData = useCallback(async () => {
    setLoading(true);
    try {
      const skip = (currentPage - 1) * itemsPerPage;
      const queryParams = new URLSearchParams({
        limit: itemsPerPage.toString(),
        skip: skip.toString(),
        search: searchTerm || ''
      });
      const response = await fetch(`/api/v1/phase2/preview-normalized-structure?${queryParams}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ...config
        })
      });
      const data = await response.json();
      if (data.success && data.preview_data) {
        // Transform the data to match our interface
        const groups = data.preview_data.map((statute: any) => ({
          _id: statute.statute_name || 'Unknown',
          Statute_Name: statute.statute_name || 'Unknown',
          Sections: statute.sections_preview || [],
          section_count: statute.section_count || 0
        }));
        setStatuteGroups(groups);
        // Set pagination info from backend response if available
        setTotalItems(data.filtered_count || data.total_statutes || 0);
        setTotalPages(data.pagination?.total_pages || Math.ceil((data.filtered_count || data.total_statutes || 0) / itemsPerPage));
        setCurrentPage(data.pagination?.current_page || currentPage);
        
        // Calculate progress metrics using TOTAL counts from backend, not just current page
        const totalStatutes = data.total_statutes || 0; // Use backend total, not current page length
        const totalSections = data.total_sections || 0; // Use backend total sections count
        const processedStatutes = totalStatutes; // All statutes are processed if they're in normalized collection
        const processedSections = totalSections; // All sections are processed
        
        const metrics: ProgressMetrics = {
          total_statutes: totalStatutes,
          processed_statutes: processedStatutes,
          total_sections: totalSections,
          processed_sections: processedSections,
          normalization_progress: totalStatutes > 0 ? (processedStatutes / totalStatutes) * 100 : 0,
          sorting_progress: totalSections > 0 ? (processedSections / totalSections) * 100 : 0,
          overall_progress: totalStatutes > 0 ? ((processedStatutes + processedSections) / (totalStatutes + totalSections)) * 100 : 0,
          estimated_time_remaining: '0 minutes',
          current_phase: 'Normalization Complete',
          last_updated: new Date().toISOString()
        };
        setProgressMetrics(metrics);
      } else {
        setStatuteGroups([]);
        setTotalItems(0);
        setTotalPages(0);
        setCurrentPage(1);
        setMessage({ type: 'error', text: data.message || 'Failed to fetch results data' });
      }
    } catch (error) {
      setStatuteGroups([]);
      setTotalItems(0);
      setTotalPages(0);
      setCurrentPage(1);
      setMessage({ type: 'error', text: 'Error fetching results data' });
    } finally {
      setLoading(false);
    }
  }, [currentPage, itemsPerPage, searchTerm, config]);

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

  // Field mapping handlers
  const updateFieldMapping = (index: number, field: keyof FieldMapping, value: any) => {
    setFieldMappings(prev => prev.map((mapping, i) => 
      i === index ? { ...mapping, [field]: value } : mapping
    ));
  };

  const addFieldMapping = () => {
    setFieldMappings(prev => [...prev, { source: '', target: '', enabled: true }]);
  };

  const removeFieldMapping = (index: number) => {
    setFieldMappings(prev => prev.filter((_, i) => i !== index));
  };

  // Toggle panel expansion
  const togglePanelExpansion = (panelId: string) => {
    const newExpanded = new Set(expandedPanels);
    if (newExpanded.has(panelId)) {
      newExpanded.delete(panelId);
    } else {
      newExpanded.add(panelId);
    }
    setExpandedPanels(newExpanded);
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

  // Execute sorting (Backend implementation completed)
  const executeSorting = async () => {
    try {
      const response = await fetch('/api/v1/phase2/apply-sorting', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          rules: sortOptions,
          scope: 'all'
        })
      });
      const data = await response.json();
      if (data.success) {
        setMessage({ type: 'success', text: `Sorting applied successfully! ${data.changes_count} documents changed.` });
        await fetchResultsData(); // Refresh data
      } else {
        setMessage({ type: 'error', text: data.message || 'Failed to apply sorting' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Error applying sorting' });
    }
  };

  // Execute cleaning (Backend implementation completed)
  const executeCleaning = async () => {
    try {
      const response = await fetch('/api/v1/phase2/apply-cleaning', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          mappings: fieldMappings,
          scope: 'all'
        })
      });
      const data = await response.json();
      if (data.success) {
        setMessage({ type: 'success', text: `Field cleaning applied successfully! ${data.changes_count} documents changed.` });
        await fetchResultsData(); // Refresh data
      } else {
        setMessage({ type: 'error', text: data.message || 'Failed to apply cleaning' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Error applying cleaning' });
    }
  };  useEffect(() => {
    fetchResultsData();
  }, [fetchResultsData]);

  const filteredStatutes = getFilteredAndSortedStatutes();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <Eye className="w-5 h-5 mr-2" />
          Results Preview - Unified Phase 2 Interface
        </h2>
        <p className="text-gray-600 mb-4">
          Centralized view for previewing, sorting, cleaning, and tracking normalization progress.
        </p>
        
        {/* Controls */}
        <div className="flex flex-wrap gap-4 items-center">
          {/* Page size dropdown */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-700">Page size:</label>
            <select
              value={itemsPerPage}
              onChange={e => {
                setItemsPerPage(Number(e.target.value));
                setCurrentPage(1); // Reset to first page on page size change
              }}
              className="px-2 py-1 border border-gray-300 rounded"
            >
              {pageSizeOptions.map(size => (
                <option key={size} value={size}>{size} per page</option>
              ))}
            </select>
          </div>
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
        <div className="mt-4 p-4 bg-gray-50 rounded-lg flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <div className="text-sm text-gray-600">
            Showing {filteredStatutes.length} of {totalItems} statutes • 
            Total sections: {filteredStatutes.reduce((sum, statute) => sum + statute.section_count, 0)} • 
            Filter: {filterType === 'all' ? 'All types' : filterType} • 
            Sort: {sortOrder === 'name' ? 'By name' : sortOrder === 'sections' ? 'By section count' : 'By type'}
          </div>
          {/* Pagination controls */}
          <div className="flex items-center gap-2">
            <button
              className="px-2 py-1 rounded border bg-white text-gray-700 disabled:opacity-50"
              disabled={currentPage === 1}
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            >Prev</button>
            <span className="text-sm text-gray-700">Page {currentPage} of {totalPages}</span>
            <button
              className="px-2 py-1 rounded border bg-white text-gray-700 disabled:opacity-50"
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            >Next</button>
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

      {/* Main Results Panel */}
      <div className="bg-white rounded-lg shadow">
        <div 
          className="p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50"
          onClick={() => togglePanelExpansion('main')}
        >
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <Eye className="w-5 h-5 mr-2" />
              Main Results Preview
            </h3>
            {expandedPanels.has('main') ? (
              <ChevronDown className="w-5 h-5 text-gray-500" />
            ) : (
              <ChevronRight className="w-5 h-5 text-gray-500" />
            )}
          </div>
        </div>
        
        {expandedPanels.has('main') && (
          <div className="p-4">
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
        )}
      </div>

      {/* Sorting Configuration Panel */}
      <div className="bg-white rounded-lg shadow">
        <div 
          className="p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50"
          onClick={() => togglePanelExpansion('sorting')}
        >
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <SortAsc className="w-5 h-5 mr-2" />
              Sorting Configuration
            </h3>
            {expandedPanels.has('sorting') ? (
              <ChevronDown className="w-5 h-5 text-gray-500" />
            ) : (
              <ChevronRight className="w-5 h-5 text-gray-500" />
            )}
          </div>
        </div>
        
        {expandedPanels.has('sorting') && (
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Sorting Options */}
              <div>
                <h4 className="font-medium text-gray-900 mb-4">Sorting Rules</h4>
                <div className="space-y-3">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={sortOptions.preambleFirst}
                      onChange={(e) => setSortOptions(prev => ({ ...prev, preambleFirst: e.target.checked }))}
                      className="mr-3"
                    />
                    <span className="text-sm text-gray-700">Preamble sections first</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={sortOptions.numericOrder}
                      onChange={(e) => setSortOptions(prev => ({ ...prev, numericOrder: e.target.checked }))}
                      className="mr-3"
                    />
                    <span className="text-sm text-gray-700">Numeric sections in order</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={sortOptions.alphabeticalFallback}
                      onChange={(e) => setSortOptions(prev => ({ ...prev, alphabeticalFallback: e.target.checked }))}
                      className="mr-3"
                    />
                    <span className="text-sm text-gray-700">Alphabetical fallback for text sections</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={sortOptions.customSortOrder}
                      onChange={(e) => setSortOptions(prev => ({ ...prev, customSortOrder: e.target.checked }))}
                      className="mr-3"
                    />
                    <span className="text-sm text-gray-700">Custom sort order (future feature)</span>
                  </label>
                </div>
                
                <div className="mt-4">
                  <button
                    onClick={executeSorting}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 flex items-center"
                  >
                    <Play className="w-4 h-4 mr-2" />
                    Execute Sorting
                  </button>
                  <p className="text-xs text-gray-500 mt-2">
                    Apply the current sorting configuration to all statutes
                  </p>
                </div>
              </div>

              {/* Sorting Preview */}
              <div>
                <h4 className="font-medium text-gray-900 mb-4">Sorting Preview</h4>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600 mb-3">
                    Current sorting applied to {filteredStatutes.length} statutes
                  </div>
                  <div className="space-y-2">
                    {filteredStatutes.slice(0, 3).map((statute, index) => (
                      <div key={index} className="text-sm">
                        <div className="font-medium">{statute.Statute_Name}</div>
                        <div className="text-gray-500">
                          {statute.section_count} sections • 
                          {statute.Sections.some((s: any) => getSectionType(s) === 'preamble') && ' Has preamble •'}
                          {statute.Sections.some((s: any) => getSectionType(s) === 'numeric') && ' Has numeric •'}
                          {statute.Sections.some((s: any) => getSectionType(s) === 'text') && ' Has text'}
                        </div>
                      </div>
                    ))}
                    {filteredStatutes.length > 3 && (
                      <div className="text-xs text-gray-500">
                        ... and {filteredStatutes.length - 3} more
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Field Mapping & Cleaning Panel */}
      <div className="bg-white rounded-lg shadow">
        <div 
          className="p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50"
          onClick={() => togglePanelExpansion('cleaning')}
        >
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <Settings className="w-5 h-5 mr-2" />
              Field Mapping & Cleaning
            </h3>
            {expandedPanels.has('cleaning') ? (
              <ChevronDown className="w-5 h-5 text-gray-500" />
            ) : (
              <ChevronRight className="w-5 h-5 text-gray-500" />
            )}
          </div>
        </div>
        
        {expandedPanels.has('cleaning') && (
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Field Mapping Editor */}
              <div>
                <h4 className="font-medium text-gray-900 mb-4">Field Mappings</h4>
                <FieldMappingEditor
                  fieldMappings={fieldMappings}
                  updateFieldMapping={updateFieldMapping}
                  addFieldMapping={addFieldMapping}
                  removeFieldMapping={removeFieldMapping}
                />
                
                <div className="mt-4">
                  <button
                    onClick={executeCleaning}
                    className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 flex items-center"
                  >
                    <Play className="w-4 h-4 mr-2" />
                    Execute Cleaning
                  </button>
                  <p className="text-xs text-gray-500 mt-2">
                    Apply the current field mappings to all statutes
                  </p>
                </div>
              </div>

              {/* Cleaning Preview */}
              <div>
                <h4 className="font-medium text-gray-900 mb-4">Cleaning Preview</h4>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600 mb-3">
                    Field mappings applied to {filteredStatutes.length} statutes
                  </div>
                  <div className="space-y-2">
                    {filteredStatutes.slice(0, 2).map((statute, index) => (
                      <div key={index} className="text-sm">
                        <div className="font-medium">{statute.Statute_Name}</div>
                        <div className="text-gray-500">
                          {statute.section_count} sections • 
                          Mapped fields: {fieldMappings.filter(m => m.enabled).length}
                        </div>
                      </div>
                    ))}
                    {filteredStatutes.length > 2 && (
                      <div className="text-xs text-gray-500">
                        ... and {filteredStatutes.length - 2} more
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Progress Panel */}
      <div className="bg-white rounded-lg shadow">
        <div 
          className="p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50"
          onClick={() => togglePanelExpansion('progress')}
        >
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <BarChart3 className="w-5 h-5 mr-2" />
              Progress Tracking
            </h3>
            {expandedPanels.has('progress') ? (
              <ChevronDown className="w-5 h-5 text-gray-500" />
            ) : (
              <ChevronRight className="w-5 h-5 text-gray-500" />
            )}
          </div>
        </div>
        
        {expandedPanels.has('progress') && progressMetrics && (
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              {/* KPI Cards */}
              <div className="bg-blue-50 p-4 rounded-lg">
                <div className="flex items-center">
                  <Database className="w-8 h-8 text-blue-600 mr-3" />
                  <div>
                    <div className="text-2xl font-bold text-blue-900">{progressMetrics.total_statutes}</div>
                    <div className="text-sm text-blue-700">Total Statutes</div>
                  </div>
                </div>
              </div>
              
              <div className="bg-green-50 p-4 rounded-lg">
                <div className="flex items-center">
                  <CheckCircle className="w-8 h-8 text-green-600 mr-3" />
                  <div>
                    <div className="text-2xl font-bold text-green-900">{progressMetrics.processed_statutes}</div>
                    <div className="text-sm text-green-700">Processed Statutes</div>
                  </div>
                </div>
              </div>
              
              <div className="bg-purple-50 p-4 rounded-lg">
                <div className="flex items-center">
                  <FileText className="w-8 h-8 text-purple-600 mr-3" />
                  <div>
                    <div className="text-2xl font-bold text-purple-900">{progressMetrics.total_sections}</div>
                    <div className="text-sm text-purple-700">Total Sections</div>
                  </div>
                </div>
              </div>
              
              <div className="bg-orange-50 p-4 rounded-lg">
                <div className="flex items-center">
                  <TrendingUp className="w-8 h-8 text-orange-600 mr-3" />
                  <div>
                    <div className="text-2xl font-bold text-orange-900">{Math.round(progressMetrics.overall_progress)}%</div>
                    <div className="text-sm text-orange-700">Overall Progress</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Progress Bars */}
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm text-gray-600 mb-1">
                  <span>Normalization Progress</span>
                  <span>{Math.round(progressMetrics.normalization_progress)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full" 
                    style={{ width: `${progressMetrics.normalization_progress}%` }}
                  ></div>
                </div>
              </div>
              
              <div>
                <div className="flex justify-between text-sm text-gray-600 mb-1">
                  <span>Sorting Progress</span>
                  <span>{Math.round(progressMetrics.sorting_progress)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-green-600 h-2 rounded-full" 
                    style={{ width: `${progressMetrics.sorting_progress}%` }}
                  ></div>
                </div>
              </div>
            </div>

            {/* Status Info */}
            <div className="mt-4 p-4 bg-gray-50 rounded-lg">
              <div className="text-sm text-gray-600">
                <div className="flex items-center mb-2">
                  <Clock className="w-4 h-4 mr-2" />
                  Last Updated: {new Date(progressMetrics.last_updated).toLocaleString()}
                </div>
                <div className="flex items-center">
                  <CheckCircle className="w-4 h-4 mr-2 text-green-600" />
                  Status: {progressMetrics.current_phase}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* History Panel */}
      <div className="bg-white rounded-lg shadow">
        <div 
          className="p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50"
          onClick={() => togglePanelExpansion('history')}
        >
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <History className="w-5 h-5 mr-2" />
              Normalization History
            </h3>
            {expandedPanels.has('history') ? (
              <ChevronDown className="w-5 h-5 text-gray-500" />
            ) : (
              <ChevronRight className="w-5 h-5 text-gray-500" />
            )}
          </div>
        </div>
        
        {expandedPanels.has('history') && (
          <div className="p-6">
            <div className="space-y-4">
              {/* Mock History Events */}
              <div className="border-l-4 border-blue-500 pl-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-gray-900">Normalization Completed</div>
                    <div className="text-sm text-gray-600">
                      {statuteGroups.length} statutes processed with {statuteGroups.reduce((sum, s) => sum + s.section_count, 0)} sections
                    </div>
                  </div>
                  <div className="text-xs text-gray-500">
                    {new Date().toLocaleString()}
                  </div>
                </div>
              </div>
              
              <div className="border-l-4 border-green-500 pl-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-gray-900">Section Sorting Applied</div>
                    <div className="text-sm text-gray-600">
                      Preamble, numeric, and text sections sorted according to rules
                    </div>
                  </div>
                  <div className="text-xs text-gray-500">
                    {new Date().toLocaleString()}
                  </div>
                </div>
              </div>
              
              <div className="border-l-4 border-purple-500 pl-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-gray-900">Field Mapping Configured</div>
                    <div className="text-sm text-gray-600">
                      {fieldMappings.filter(m => m.enabled).length} active field mappings
                    </div>
                  </div>
                  <div className="text-xs text-gray-500">
                    {new Date().toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
            
            <div className="mt-4 p-3 bg-blue-50 rounded text-sm text-blue-800">
              <strong>Note:</strong> This is a preview of normalization history. 
              Full history tracking will be implemented with backend integration.
            </div>
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
