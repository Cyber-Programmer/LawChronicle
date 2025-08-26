import React, { useState, useEffect } from 'react';
import { FileText, TrendingUp, Search, BarChart3, Download, AlertTriangle } from 'lucide-react';
import axios from 'axios';

interface StatuteAnalysisProps {
  databaseInfo: any;
  lastRefresh: Date | null;
}

interface StatuteNamesResponse {
  field_used: string | null;
  count: number;
  statute_names: string[];
  name_distribution?: Record<string, number>;
  limit?: number;
  timestamp: string;
}

const StatuteAnalysis: React.FC<StatuteAnalysisProps> = ({
  databaseInfo,
  lastRefresh
}) => {
  const [statuteData, setStatuteData] = useState<StatuteNamesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showAllNames, setShowAllNames] = useState(false);
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);

  const fetchStatuteNames = async (newLimit = limit, newOffset = offset) => {
    if (databaseInfo.status !== 'connected') return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await axios.get('/api/v1/phase1/statute-names', {
        params: { limit: newLimit, offset: newOffset }
      });
      setStatuteData(response.data);
      setLimit(newLimit);
      setOffset(newOffset);
    } catch (error: any) {
      setError(error.response?.data?.detail || error.message || 'Failed to fetch statute names');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (databaseInfo.status === 'connected') {
      fetchStatuteNames(limit, offset);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [databaseInfo.status, lastRefresh]);

  const exportStatuteData = () => {
    if (!statuteData) return;
    
    const dataStr = JSON.stringify(statuteData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `statute-analysis-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const filteredNames = statuteData && Array.isArray(statuteData.statute_names)
    ? statuteData.statute_names.filter(name =>
        typeof name === 'string' && name.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : [];

  const sortedDistribution = statuteData?.name_distribution 
    ? Object.entries(statuteData.name_distribution)
        .sort(([,a], [,b]) => b - a)
        .slice(0, showAllNames ? undefined : 10)
    : [];

  if (databaseInfo.status !== 'connected') {
    return (
      <div className="text-center py-8">
        <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">Database Not Connected</h3>
        <p className="text-gray-600">Please connect to a database to view statute analysis</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="text-center py-8">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">Analyzing Statutes</h3>
        <p className="text-gray-600">Please wait while we analyze the statute names...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <div className="text-red-400 mb-4">
          <FileText className="w-12 h-12 mx-auto" />
        </div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">Analysis Failed</h3>
        <p className="text-red-600 mb-4">{error}</p>
        <button
          onClick={() => fetchStatuteNames()}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        >
          Retry Analysis
        </button>
      </div>
    );
  }

  if (!statuteData) {
    return (
      <div className="text-center py-8">
        <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">No Statute Data</h3>
        <p className="text-gray-600 mb-4">Click the button below to analyze statute names</p>
        <button
          onClick={() => fetchStatuteNames()}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        >
          <TrendingUp className="w-4 h-4 mr-2" />
          Analyze Statutes
        </button>
      </div>
    );
  }

  // Pagination controls
  const totalCount = statuteData?.count || 0;
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(totalCount / limit));

  const handlePrev = () => {
    if (offset - limit >= 0) {
      fetchStatuteNames(limit, offset - limit);
    }
  };
  const handleNext = () => {
    if (offset + limit < totalCount) {
      fetchStatuteNames(limit, offset + limit);
    }
  };
  const handleLimitChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newLimit = parseInt(e.target.value, 10);
    fetchStatuteNames(newLimit, 0);
  };

  return (
    <div>
      {/* Summary Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Statute Analysis</h3>
          <p className="text-sm text-gray-600">
            {typeof statuteData?.count === 'number'
              ? statuteData.count.toLocaleString()
              : '0'} unique statutes found
          </p>
        </div>
        
        <div className="flex items-center space-x-3">
          <button
            onClick={() => fetchStatuteNames()}
            className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
          >
            <TrendingUp className="w-4 h-4 mr-2" />
            Refresh
          </button>
          
          <button
            onClick={exportStatuteData}
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-success-600 hover:bg-success-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-success-500"
          >
            <Download className="w-4 h-4 mr-2" />
            Export
          </button>
        </div>
      </div>

      {/* Field Information */}
      {statuteData.field_used && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <BarChart3 className="w-5 h-5 text-blue-600" />
            <div>
              <h4 className="text-sm font-medium text-blue-900">Analysis Field</h4>
              <p className="text-sm text-blue-700">
                Using field: <code className="bg-blue-100 px-2 py-1 rounded">{statuteData.field_used}</code>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search statute names..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <div className="bg-gray-50 p-4 rounded-lg border">
          <div className="flex items-center space-x-2">
            <FileText className="w-5 h-5 text-primary-600" />
            <div>
              <p className="text-sm text-gray-600">Total Unique</p>
              <p className="text-2xl font-bold text-gray-900">{
                typeof statuteData?.count === 'number'
                  ? statuteData.count.toLocaleString()
                  : '0'
              }</p>
            </div>
          </div>
        </div>
        
        <div className="bg-gray-50 p-4 rounded-lg border">
          <div className="flex items-center space-x-2">
            <BarChart3 className="w-5 h-5 text-success-600" />
            <div>
              <p className="text-sm text-gray-600">Sample Size</p>
              <p className="text-2xl font-bold text-gray-900">{
                Array.isArray(statuteData?.statute_names) && typeof statuteData.statute_names.length === 'number'
                  ? statuteData.statute_names.length.toLocaleString()
                  : '0'
              }</p>
            </div>
          </div>
        </div>
      </div>

      {/* Name Distribution Chart */}
  {statuteData.name_distribution && sortedDistribution.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-gray-900">Top Statute Distribution</h4>
            <button
              onClick={() => setShowAllNames(!showAllNames)}
              className="text-sm text-primary-600 hover:text-primary-700"
            >
              {showAllNames ? 'Show Top 10' : 'Show All'}
            </button>
          </div>
          
          <div className="space-y-2">
            {sortedDistribution.map(([name, count]) => (
              <div key={name} className="flex items-center space-x-3">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 truncate" title={name}>
                    {name}
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-24 bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                      style={{ 
                        width: `${(
                          statuteData.name_distribution
                            ? (count / Math.max(...Object.values(statuteData.name_distribution))) * 100
                            : 0
                        )}%` 
                      }}
                    ></div>
                  </div>
                  <span className="text-sm text-gray-600 w-12 text-right">
                    {typeof count === 'number' ? count.toLocaleString() : '0'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sample Names */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-medium text-gray-900">Sample Statute Names</h4>
          <div className="flex items-center space-x-2">
            <button
              onClick={handlePrev}
              disabled={offset === 0}
              className="px-2 py-1 text-sm rounded border bg-white text-gray-700 disabled:opacity-50"
            >Prev</button>
            <span className="text-xs text-gray-600">Page {currentPage} of {totalPages}</span>
            <button
              onClick={handleNext}
              disabled={offset + limit >= totalCount}
              className="px-2 py-1 text-sm rounded border bg-white text-gray-700 disabled:opacity-50"
            >Next</button>
            <select value={limit} onChange={handleLimitChange} className="ml-2 px-2 py-1 text-sm border rounded">
              {[10, 20, 50, 100].map(size => (
                <option key={size} value={size}>{size} / page</option>
              ))}
            </select>
          </div>
        </div>
        <div className="space-y-2">
          {filteredNames.length > 0 ? (
            filteredNames.map((name, index) => (
              <div key={index} className="p-3 bg-gray-50 rounded-lg border">
                <div className="text-sm text-gray-900">{name}</div>
                {statuteData?.name_distribution &&
                  typeof statuteData.name_distribution[name] === 'number' && (
                    <div className="text-xs text-gray-500 mt-1">
                      Count: {
                        typeof statuteData.name_distribution[name] === 'number'
                          ? statuteData.name_distribution[name].toLocaleString()
                          : '0'
                      }
                    </div>
                  )}
              </div>
            ))
          ) : (
            <div className="text-center py-4 text-gray-500">
              {searchTerm ? 'No statute names match your search' : 'No sample names available'}
            </div>
          )}
        </div>
      </div>

      {/* No Field Warning */}
      {!statuteData.field_used && (
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 text-yellow-600" />
            <div>
              <h4 className="text-sm font-medium text-yellow-900">Field Detection</h4>
              <p className="text-sm text-yellow-700">
                Could not automatically detect a suitable field for statute names. 
                The analysis may be incomplete.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Last Updated */}
      <div className="mt-6 text-center text-sm text-gray-500">
        Last updated: {statuteData.timestamp ? new Date(statuteData.timestamp).toLocaleString() : 'Unknown'}
      </div>
    </div>
  );
};

export default StatuteAnalysis;
