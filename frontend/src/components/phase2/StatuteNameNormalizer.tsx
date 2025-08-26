import React, { useState, useEffect, useCallback } from 'react';
import { FileText, Edit3, Save, X, Search, RefreshCw, AlertTriangle, CheckCircle, Eye, ChevronDown, ChevronRight, BookOpen, FileText as SectionIcon } from 'lucide-react';

interface StatuteGroup {
  _id: string;
  Statute_Name: string;
  Sections: any[];
  section_count: number;
}

interface StatuteNameNormalizerProps {
  config: {
    source_collection: string;
    target_collection: string;
    database_name?: string;
    sorted_collection: string;
  };
}

const StatuteNameNormalizer: React.FC<StatuteNameNormalizerProps> = ({ config }) => {
  const [statuteGroups, setStatuteGroups] = useState<StatuteGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [selectedGroups, setSelectedGroups] = useState<Set<string>>(new Set());
  const [batchEditMode, setBatchEditMode] = useState(false);
  const [batchNewName, setBatchNewName] = useState('');
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(100);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  // Fetch statute groups from normalized collection
  const fetchStatuteGroups = useCallback(async (page: number = 1, limit: number = 100, search: string = '') => {
    setLoading(true);
    try {
      const skip = (page - 1) * limit;
      const queryParams = new URLSearchParams({
        limit: limit.toString(),
        skip: skip.toString(),
        search: search
      });
      const response = await fetch(`/api/v1/phase2/detailed-normalized-structure?${queryParams}`, {
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
      if (data.success && data.detailed_data) {
        // Transform the data to match our interface
        const groups = data.detailed_data.map((statute: any) => ({
          _id: statute.statute_name || 'Unknown',
          Statute_Name: statute.statute_name || 'Unknown',
          Sections: statute.sections || [],
          section_count: statute.section_count || 0
        }));
        setStatuteGroups(groups);
        // Set pagination info from backend response
        setTotalItems(data.filtered_count || data.total_statutes || 0);
        setTotalPages(data.pagination?.total_pages || Math.ceil((data.filtered_count || data.total_statutes || 0) / limit));
        setCurrentPage(data.pagination?.current_page || page);
      } else {
        setStatuteGroups([]);
        setTotalItems(0);
        setTotalPages(0);
        setCurrentPage(1);
        setMessage({ type: 'error', text: data.message || 'Failed to fetch statute groups' });
      }
    } catch (error) {
      setStatuteGroups([]);
      setTotalItems(0);
      setTotalPages(0);
      setCurrentPage(1);
      setMessage({ type: 'error', text: 'Error fetching statute groups' });
    } finally {
      setLoading(false);
    }
  }, [config]);

  // Pagination handlers
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    fetchStatuteGroups(page, itemsPerPage, searchTerm);
  };

  const handleItemsPerPageChange = (newItemsPerPage: number) => {
    setItemsPerPage(newItemsPerPage);
    setCurrentPage(1);
    fetchStatuteGroups(1, newItemsPerPage, searchTerm);
  };

  const handleSearch = (term: string) => {
    setSearchTerm(term);
    setCurrentPage(1);
    fetchStatuteGroups(1, itemsPerPage, term);
  };

  const refreshData = () => {
    fetchStatuteGroups(currentPage, itemsPerPage, searchTerm);
  };

  // Update a statute name (this would need a new backend endpoint)
  const updateStatuteName = async (oldName: string, newName: string) => {
    try {
      // For now, show a message that this feature needs backend implementation
      setMessage({ 
        type: 'error', 
        text: 'Statute name editing requires backend implementation for the new grouped schema' 
      });
      
      // TODO: Implement backend endpoint to update statute names in grouped structure
      // This would need to:
      // 1. Find all documents with the old statute name
      // 2. Update the Statute_Name field
      // 3. Re-run normalization if needed
      
    } catch (error) {
      setMessage({ type: 'error', text: 'Error updating statute name' });
    }
  };

  // Handle edit start
  const startEdit = (statuteGroup: StatuteGroup) => {
    setEditingId(statuteGroup._id);
    setEditingName(statuteGroup.Statute_Name);
  };

  // Handle edit save
  const saveEdit = async () => {
    if (editingId && editingName.trim()) {
      await updateStatuteName(editingId, editingName.trim());
      setEditingId(null);
      setEditingName('');
    }
  };

  // Handle edit cancel
  const cancelEdit = () => {
    setEditingId(null);
    setEditingName('');
  };

  // Handle group selection
  const toggleSelection = (groupId: string) => {
    const newSelection = new Set(selectedGroups);
    if (newSelection.has(groupId)) {
      newSelection.delete(groupId);
    } else {
      newSelection.add(groupId);
    }
    setSelectedGroups(newSelection);
  };

  // Handle batch edit
  const handleBatchEdit = async () => {
    if (selectedGroups.size === 0 || !batchNewName.trim()) {
      setMessage({ type: 'error', text: 'Please select groups and enter a new name' });
      return;
    }

    // For now, show a message that this feature needs backend implementation
    setMessage({ 
      type: 'error', 
      text: 'Batch editing requires backend implementation for the new grouped schema' 
    });
  };

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

  // Toggle section expansion
  const toggleSectionExpansion = (sectionId: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(sectionId)) {
      newExpanded.delete(sectionId);
    } else {
      newExpanded.add(sectionId);
    }
    setExpandedSections(newExpanded);
  };

  // Filter statutes based on search term
  const filteredStatutes = statuteGroups.filter(statute => {
    // Add safe checks before calling string methods
    if (!statute.Statute_Name || typeof statute.Statute_Name !== 'string') {
      return false; // Skip statutes with invalid names
    }
    return statute.Statute_Name.toLowerCase().includes(searchTerm.toLowerCase());
  });

  useEffect(() => {
    fetchStatuteGroups();
  }, [fetchStatuteGroups]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <FileText className="w-5 h-5 mr-2" />
          Statute Names - Grouped View
        </h2>
        <p className="text-gray-600 mb-4">
          View and manage statute names in the new grouped structure. Each statute contains multiple sections.
        </p>
        
        {/* Search and Controls */}
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-64">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                placeholder="Search statute names..."
                value={searchTerm}
                onChange={(e) => handleSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          
          {/* Items per page selector */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Show:</span>
            <select
              value={itemsPerPage}
              onChange={(e) => handleItemsPerPageChange(Number(e.target.value))}
              className="border border-gray-300 rounded px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={75}>75</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </div>
          
          {/* Pagination info */}
          <div className="text-sm text-gray-600">
            {currentPage} – {Math.min(currentPage * itemsPerPage, totalItems)} of {totalItems.toLocaleString()}
          </div>
          
          <button
            onClick={refreshData}
            disabled={loading}
            className="bg-gray-600 text-white px-4 py-2 rounded-lg hover:bg-gray-700 disabled:opacity-50 flex items-center"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Batch Edit Controls */}
      {selectedGroups.size > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div className="text-blue-800">
              {selectedGroups.size} statute group(s) selected
            </div>
            <div className="flex items-center space-x-2">
              <input
                type="text"
                placeholder="New statute name..."
                value={batchNewName}
                onChange={(e) => setBatchNewName(e.target.value)}
                className="px-3 py-1 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleBatchEdit}
                className="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700"
              >
                <Save className="w-4 h-4 mr-1" />
                Update Selected
              </button>
            </div>
          </div>
        </div>
      )}

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

      {/* Statute Groups List */}
      <div className="bg-white rounded-lg shadow">
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
            Loading statute groups...
          </div>
        ) : filteredStatutes.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            {searchTerm ? 'No statutes found matching your search.' : 'No statute groups found.'}
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {filteredStatutes.map((statute) => (
              <div key={statute._id} className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={selectedGroups.has(statute._id)}
                      onChange={() => toggleSelection(statute._id)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    
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
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    {editingId === statute._id ? (
                      <>
                        <input
                          type="text"
                          value={editingName}
                          onChange={(e) => setEditingName(e.target.value)}
                          className="px-2 py-1 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
                        />
                        <button
                          onClick={saveEdit}
                          className="text-green-600 hover:text-green-800"
                        >
                          <Save className="w-4 h-4" />
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="text-gray-600 hover:text-gray-800"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => startEdit(statute)}
                        className="text-blue-600 hover:text-blue-800"
                        title="Edit statute name"
                      >
                        <Edit3 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
                
                {/* Expanded Sections View */}
                {expandedGroups.has(statute._id) && (
                  <div className="mt-3 ml-8 space-y-2">
                    <div className="text-sm text-gray-600 font-medium">Sections:</div>
                    {statute.Sections && statute.Sections.length > 0 ? (
                      <div className="space-y-2">
                        {statute.Sections.map((section: any, index: number) => {
                          const sectionId = `${statute._id}-section-${index}`;
                          const isExpanded = expandedSections.has(sectionId);
                          
                          // Get section number and definition from additional_fields
                          const sectionNumber = section.additional_fields?.Section || section.number || `${index + 1}`;
                          const sectionDefinition = section.additional_fields?.Definition || section.definition || 'No title';
                          const sectionContent = section.Statute || section.content || 'No content available';
                          
                          return (
                            <div key={index} className="border border-gray-200 rounded-lg">
                              <div className="bg-gray-50 p-3 flex items-center justify-between">
                                <button
                                  onClick={() => toggleSectionExpansion(sectionId)}
                                  className="flex items-center space-x-2 text-left hover:text-blue-600 flex-1"
                                >
                                  {isExpanded ? (
                                    <ChevronDown className="w-4 h-4" />
                                  ) : (
                                    <ChevronRight className="w-4 h-4" />
                                  )}
                                  <SectionIcon className="w-4 h-4" />
                                  <span className="font-medium text-gray-700">
                                    {sectionNumber} : {sectionDefinition}
                                  </span>
                                </button>
                                <div className="text-xs text-gray-500">
                                  {sectionContent.length} chars
                                </div>
                              </div>
                              
                              {isExpanded && (
                                <div className="p-4 border-t border-gray-200 bg-white">
                                  <div className="space-y-3">
                                    {/* Section Header Info */}
                                    <div className="bg-blue-50 p-3 rounded-lg">
                                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                        <div>
                                          <h4 className="text-sm font-semibold text-blue-800 mb-1">Section Number:</h4>
                                          <p className="text-sm text-blue-700 font-mono">
                                            {sectionNumber}
                                          </p>
                                        </div>
                                        <div>
                                          <h4 className="text-sm font-semibold text-blue-800 mb-1">Section Title:</h4>
                                          <p className="text-sm text-blue-700">
                                            {sectionDefinition}
                                          </p>
                                        </div>
                                      </div>
                                    </div>
                                    
                                    {/* Full Statute Content */}
                                    <div>
                                      <h4 className="text-sm font-semibold text-gray-800 mb-2">Full Statute Text:</h4>
                                      <div className="text-sm text-gray-700 bg-gray-50 p-4 rounded-lg max-h-96 overflow-y-auto border">
                                        <pre className="whitespace-pre-wrap font-sans leading-relaxed">
                                          {sectionContent}
                                        </pre>
                                      </div>
                                    </div>
                                    
                                    {/* Additional Metadata */}
                                    {section.additional_fields && Object.keys(section.additional_fields).length > 2 && (
                                      <div>
                                        <h4 className="text-sm font-semibold text-gray-800 mb-2">Additional Information:</h4>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                          {Object.entries(section.additional_fields).map(([key, value]) => {
                                            // Skip already displayed fields
                                            if (['Section', 'Definition'].includes(key)) {
                                              return null;
                                            }
                                            
                                            // Skip empty or null values
                                            if (!value || (typeof value === 'string' && value.trim() === '')) {
                                              return null;
                                            }
                                            
                                            return (
                                              <div key={key} className="bg-yellow-50 p-2 rounded">
                                                <h5 className="text-xs font-semibold text-yellow-800 mb-1 capitalize">
                                                  {key.replace(/_/g, ' ')}:
                                                </h5>
                                                <p className="text-xs text-yellow-700">
                                                  {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                                                </p>
                                              </div>
                                            );
                                          })}
                                        </div>
                                      </div>
                                    )}
                                  </div>
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
        
        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4 mt-6 p-4 bg-gray-50 rounded-lg">
            <div className="text-sm text-gray-600">
              Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, totalItems)} of {totalItems.toLocaleString()} results
            </div>
            
            <div className="flex items-center gap-2">
              {/* Previous button */}
              <button
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1}
                className="px-3 py-2 text-sm border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
              >
                Previous
              </button>
              
              {/* Page numbers */}
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  let page: number;
                  if (totalPages <= 7) {
                    page = i + 1;
                  } else if (currentPage <= 4) {
                    page = i + 1;
                  } else if (currentPage >= totalPages - 3) {
                    page = totalPages - 6 + i;
                  } else {
                    page = currentPage - 3 + i;
                  }
                  
                  return (
                    <button
                      key={page}
                      onClick={() => handlePageChange(page)}
                      className={`px-3 py-2 text-sm border rounded-lg ${
                        currentPage === page
                          ? 'bg-blue-500 text-white border-blue-500'
                          : 'border-gray-300 hover:bg-gray-100'
                      }`}
                    >
                      {page}
                    </button>
                  );
                })}
              </div>
              
              {/* Next button */}
              <button
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
                className="px-3 py-2 text-sm border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Summary */}
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="text-sm text-gray-600">
          {searchTerm ? (
            <>Found {totalItems.toLocaleString()} statute group(s) matching "{searchTerm}"</>
          ) : (
            <>Total: {totalItems.toLocaleString()} statute group(s)</>
          )}
          {totalPages > 1 && (
            <> • Page {currentPage} of {totalPages}</>
          )}
        </div>
      </div>
    </div>
  );
};

export default StatuteNameNormalizer;
