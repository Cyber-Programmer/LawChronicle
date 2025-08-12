import React, { useState, useEffect, useCallback } from 'react';
import { FileText, Edit3, Save, X, Search, RefreshCw, AlertTriangle, CheckCircle, Eye, ChevronDown, ChevronRight } from 'lucide-react';

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
    cleaned_collection: string;
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

  // Fetch statute groups from normalized collection
  const fetchStatuteGroups = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/phase2/preview-normalized-structure?limit=1000', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(config)
      });
      const data = await response.json();
      
      if (data.success && data.preview_data) {
        // Transform the data to match our interface
        // Backend returns 'statute_name' (lowercase), not 'Statute_Name'
        const groups = data.preview_data.map((statute: any) => ({
          _id: statute.statute_name || 'Unknown', // Use statute_name as ID since it's unique
          Statute_Name: statute.statute_name || 'Unknown', // Map to our interface
          Sections: statute.sections_preview || [], // Backend returns sections_preview
          section_count: statute.section_count || 0
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
  }, [config]);

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
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          
          <button
            onClick={fetchStatuteGroups}
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
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                        {statute.Sections.map((section: any, index: number) => (
                          <div key={index} className="bg-gray-50 p-2 rounded text-sm">
                            <div className="font-medium text-gray-700">
                              {section.number || `Section ${index + 1}`}
                            </div>
                            <div className="text-gray-600 truncate">
                              {section.definition || section.content || 'No content'}
                            </div>
                          </div>
                        ))}
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
          Total: {filteredStatutes.length} statute group(s)
          {searchTerm && ` (filtered from ${statuteGroups.length} total)`}
        </div>
      </div>
    </div>
  );
};

export default StatuteNameNormalizer;
