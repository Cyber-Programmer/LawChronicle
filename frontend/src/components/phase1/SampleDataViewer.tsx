import React, { useState, useEffect } from 'react';
import { Activity, Search, ChevronLeft, ChevronRight, Download, Eye, EyeOff, Filter } from 'lucide-react';
import axios from 'axios';

interface SampleDataViewerProps {
  databaseInfo: any;
  lastRefresh: Date | null;
}

interface Document {
  [key: string]: any;
}

interface SampleDataResponse {
  documents: Document[];
  pagination: {
    current_page: number;
    page_size: number;
    total_documents: number;
    total_pages: number;
    has_next: boolean;
    has_previous: boolean;
  };
  timestamp: string;
}

const SampleDataViewer: React.FC<SampleDataViewerProps> = ({
  databaseInfo,
  lastRefresh
}) => {
  const [sampleData, setSampleData] = useState<SampleDataResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [searchTerm, setSearchTerm] = useState('');
  const [fieldFilter, setFieldFilter] = useState('');
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [expandedDocuments, setExpandedDocuments] = useState<Set<number>>(new Set());

  const fetchSampleData = async (page: number = 1, size: number = pageSize) => {
    if (databaseInfo.status !== 'connected') return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: size.toString()
      });
      
      if (fieldFilter) {
        params.append('field_filter', fieldFilter);
      }
      
      const response = await axios.get(`/api/v1/phase1/sample-data?${params}`);
      setSampleData(response.data);
      setCurrentPage(page);
    } catch (error: any) {
      setError(error.response?.data?.detail || error.message || 'Failed to fetch sample data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (databaseInfo.status === 'connected') {
      fetchSampleData(1, pageSize);
    }
  }, [databaseInfo.status, lastRefresh]);

  const handlePageChange = (newPage: number) => {
    fetchSampleData(newPage, pageSize);
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    fetchSampleData(1, newSize);
  };

  const handleSearch = () => {
    fetchSampleData(1, pageSize);
  };

  const toggleDocumentExpansion = (index: number) => {
    const newExpanded = new Set(expandedDocuments);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedDocuments(newExpanded);
  };

  const exportSampleData = () => {
    if (!sampleData) return;
    
    const dataStr = JSON.stringify(sampleData.documents, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `sample-data-page-${currentPage}-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const formatFieldValue = (value: any): string => {
    if (value === null || value === undefined) return 'null';
    if (typeof value === 'object') return JSON.stringify(value);
    if (typeof value === 'string' && value.length > 100) {
      return `${value.substring(0, 100)}...`;
    }
    return String(value);
  };

  if (databaseInfo.status !== 'connected') {
    return (
      <div className="text-center py-8">
        <Activity className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">Database Not Connected</h3>
        <p className="text-gray-600">Please connect to a database to view sample data</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="text-center py-8">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">Loading Sample Data</h3>
        <p className="text-gray-600">Please wait while we fetch the documents...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <div className="text-red-400 mb-4">
          <Activity className="w-12 h-12 mx-auto" />
        </div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">Failed to Load Data</h3>
        <p className="text-red-600 mb-4">{error}</p>
        <button
          onClick={() => fetchSampleData(1, pageSize)}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!sampleData || sampleData.documents.length === 0) {
    return (
      <div className="text-center py-8">
        <Activity className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">No Sample Data</h3>
        <p className="text-gray-600 mb-4">No documents found in the collection</p>
        <button
          onClick={() => fetchSampleData(1, pageSize)}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        >
          Refresh
        </button>
      </div>
    );
  }

  const allFields = sampleData.documents.length > 0 
    ? Object.keys(sampleData.documents[0]) 
    : [];

  return (
    <div>
      {/* Controls Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6 space-y-4 sm:space-y-0">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Sample Documents</h3>
          <p className="text-sm text-gray-600">
            Showing {sampleData.pagination.current_page} of {sampleData.pagination.total_pages} pages
            ({sampleData.pagination.total_documents.toLocaleString()} total documents)
          </p>
        </div>
        
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
            className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
          >
            <Filter className="w-4 h-4 mr-2" />
            Filters
          </button>
          
          <button
            onClick={exportSampleData}
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-success-600 hover:bg-success-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-success-500"
          >
            <Download className="w-4 h-4 mr-2" />
            Export
          </button>
        </div>
      </div>

      {/* Advanced Filters */}
      {showAdvancedFilters && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <h4 className="text-sm font-medium text-gray-900 mb-3">Advanced Filters</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-gray-700 mb-1">Search Term</label>
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search in documents..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            
            <div>
              <label className="block text-sm text-gray-700 mb-1">Field Filter</label>
              <select
                value={fieldFilter}
                onChange={(e) => setFieldFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              >
                <option value="">All Fields</option>
                {allFields.map(field => (
                  <option key={field} value={field}>{field}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm text-gray-700 mb-1">Page Size</label>
              <select
                value={pageSize}
                onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              >
                <option value={5}>5 per page</option>
                <option value={10}>10 per page</option>
                <option value={25}>25 per page</option>
                <option value={50}>50 per page</option>
                <option value={100}>100 per page</option>
              </select>
            </div>
          </div>
          
          <div className="mt-4">
            <button
              onClick={handleSearch}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              <Search className="w-4 h-4 mr-2" />
              Apply Filters
            </button>
          </div>
        </div>
      )}

      {/* Documents Grid */}
      <div className="space-y-4">
        {sampleData.documents.map((document, index) => (
          <div key={index} className="border border-gray-200 rounded-lg overflow-hidden">
            {/* Document Header */}
            <div 
              className="px-4 py-3 bg-gray-50 border-b border-gray-200 cursor-pointer hover:bg-gray-100 transition-colors duration-200"
              onClick={() => toggleDocumentExpansion(index)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <span className="text-sm font-medium text-gray-900">
                    Document #{((currentPage - 1) * pageSize) + index + 1}
                  </span>
                  <span className="text-xs text-gray-500">
                    {Object.keys(document).length} fields
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  {expandedDocuments.has(index) ? (
                    <EyeOff className="w-4 h-4 text-gray-500" />
                  ) : (
                    <Eye className="w-4 h-4 text-gray-500" />
                  )}
                </div>
              </div>
            </div>

            {/* Document Content */}
            {expandedDocuments.has(index) && (
              <div className="p-4 bg-white">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {Object.entries(document).map(([field, value]) => (
                    <div key={field} className="space-y-1">
                      <label className="block text-xs font-medium text-gray-700 uppercase tracking-wide">
                        {field}
                      </label>
                      <div className="text-sm text-gray-900 bg-gray-50 px-3 py-2 rounded border">
                        {formatFieldValue(value)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Pagination */}
      {sampleData.pagination.total_pages > 1 && (
        <div className="mt-6 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-sm text-gray-700">
              Showing {((currentPage - 1) * pageSize) + 1} to{' '}
              {Math.min(currentPage * pageSize, sampleData.pagination.total_documents)} of{' '}
              {sampleData.pagination.total_documents.toLocaleString()} results
            </span>
          </div>
          
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={!sampleData.pagination.has_previous}
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4 mr-1" />
              Previous
            </button>
            
            <span className="text-sm text-gray-700">
              Page {currentPage} of {sampleData.pagination.total_pages}
            </span>
            
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={!sampleData.pagination.has_next}
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="w-4 h-4 ml-1" />
            </button>
          </div>
        </div>
      )}

      {/* Last Updated */}
      <div className="mt-6 text-center text-sm text-gray-500">
        Last updated: {sampleData.timestamp ? new Date(sampleData.timestamp).toLocaleString() : 'Unknown'}
      </div>
    </div>
  );
};

export default SampleDataViewer;
