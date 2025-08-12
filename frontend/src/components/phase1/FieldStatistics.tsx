import React, { useState, useEffect, useCallback } from 'react';
import { BarChart3, TrendingUp, AlertTriangle, CheckCircle, XCircle, Download, Database } from 'lucide-react';
import axios from 'axios';

interface FieldStatisticsProps {
  databaseInfo: any;
  isAnalyzing: boolean;
  onAnalysisStart: () => void;
  onAnalysisComplete: () => void;
}

interface FieldStat {
  total_documents: number;
  field_present: number;
  non_empty_values: number;
  coverage_percentage: number;
  non_empty_percentage: number;
  missing_count: number;
  empty_count: number;
  sample_values: string[];
  field_type: string;
}

interface FieldStatsResponse {
  total_documents?: number;
  total_fields?: number;
  field_statistics?: Record<string, FieldStat>;
  timestamp?: string;
  // For empty/error cases
  message?: string;
  fields?: Record<string, any>;
}

const FieldStatistics: React.FC<FieldStatisticsProps> = ({
  databaseInfo,
  isAnalyzing,
  onAnalysisStart,
  onAnalysisComplete
}) => {
  const [fieldStats, setFieldStats] = useState<FieldStatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState<string | null>(null);

  const fetchFieldStats = useCallback(async () => {
    if (databaseInfo.status !== 'connected') return;
    
    setIsLoading(true);
    setError(null);
    onAnalysisStart();
    
    try {
      const response = await axios.get('/api/v1/phase1/field-stats');
      setFieldStats(response.data);
    } catch (error: any) {
      setError(error.response?.data?.detail || error.message || 'Failed to fetch field statistics');
    } finally {
      setIsLoading(false);
      onAnalysisComplete();
    }
  }, [databaseInfo.status, onAnalysisStart, onAnalysisComplete]);

  useEffect(() => {
    if (databaseInfo.status === 'connected' && !fieldStats) {
      fetchFieldStats();
    }
  }, [databaseInfo.status, fieldStats, fetchFieldStats]);

  const getCoverageColor = (percentage: number) => {
    if (percentage >= 80) return 'bg-green-500';
    if (percentage >= 60) return 'bg-yellow-500';
    if (percentage >= 40) return 'bg-orange-500';
    return 'bg-red-500';
  };

  const getCoverageTextColor = (percentage: number) => {
    if (percentage >= 80) return 'text-green-700';
    if (percentage >= 60) return 'text-yellow-700';
    if (percentage >= 40) return 'text-orange-700';
    return 'text-red-700';
  };

  const exportFieldStats = () => {
    if (!fieldStats) return;
    
    const dataStr = JSON.stringify(fieldStats, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `field-statistics-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (databaseInfo.status !== 'connected') {
    return (
      <div className="text-center py-8">
        <Database className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">Database Not Connected</h3>
        <p className="text-gray-600">Please connect to a database to view field statistics</p>
      </div>
    );
  }

  if (isLoading || isAnalyzing) {
    return (
      <div className="text-center py-8">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">Analyzing Database</h3>
        <p className="text-gray-600">Please wait while we analyze the field structure...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">Analysis Failed</h3>
        <p className="text-red-600 mb-4">{error}</p>
        <button
          onClick={fetchFieldStats}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        >
          <TrendingUp className="w-4 h-4 mr-2" />
          Retry Analysis
        </button>
      </div>
    );
  }

  if (!fieldStats) {
    return (
      <div className="text-center py-8">
        <BarChart3 className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">No Field Statistics</h3>
        <p className="text-gray-600 mb-4">Click the button below to analyze the database structure</p>
        <button
          onClick={fetchFieldStats}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        >
          <TrendingUp className="w-4 h-4 mr-2" />
          Analyze Fields
        </button>
      </div>
    );
  }

  // Handle both field_statistics (when data exists) and fields (when empty)
  const statisticsData = fieldStats?.field_statistics || fieldStats?.fields || {};
  const fields = Object.entries(statisticsData);
  const sortedFields = fields.sort((a, b) => b[1]?.coverage_percentage - a[1]?.coverage_percentage);

  // Show message for empty collection
  if (fieldStats?.message && fields.length === 0) {
    return (
      <div className="text-center py-8">
        <Database className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">No Data Available</h3>
        <p className="text-gray-600">{fieldStats.message}</p>
        <p className="text-sm text-gray-500 mt-2">Add some documents to the collection to see field statistics</p>
      </div>
    );
  }

  return (
    <div>
      {/* Summary Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Field Coverage Analysis</h3>
          <p className="text-sm text-gray-600">
            {fieldStats.total_fields || 0} fields across {(fieldStats.total_documents || 0).toLocaleString()} documents
          </p>
        </div>
        
        <div className="flex items-center space-x-3">
          <button
            onClick={fetchFieldStats}
            className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
          >
            <TrendingUp className="w-4 h-4 mr-2" />
            Refresh
          </button>
          
          <button
            onClick={exportFieldStats}
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-success-600 hover:bg-success-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-success-500"
          >
            <Download className="w-4 h-4 mr-2" />
            Export
          </button>
        </div>
      </div>

      {/* Field Statistics Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {sortedFields.map(([fieldName, stats]) => (
          <div
            key={fieldName}
            className={`p-4 border rounded-lg cursor-pointer transition-all duration-200 ${
              selectedField === fieldName 
                ? 'border-primary-300 bg-primary-50' 
                : 'border-gray-200 hover:border-gray-300'
            }`}
            onClick={() => setSelectedField(selectedField === fieldName ? null : fieldName)}
          >
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-medium text-gray-900">{fieldName}</h4>
              <div className="flex items-center space-x-2">
                <span className={`text-sm font-medium ${getCoverageTextColor(stats.coverage_percentage)}`}>
                  {stats.coverage_percentage}%
                </span>
                {stats.coverage_percentage >= 80 ? (
                  <CheckCircle className="w-4 h-4 text-green-500" />
                ) : stats.coverage_percentage >= 60 ? (
                  <AlertTriangle className="w-4 h-4 text-yellow-500" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-500" />
                )}
              </div>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-gray-200 rounded-full h-2 mb-3">
              <div
                className={`h-2 rounded-full ${getCoverageColor(stats.coverage_percentage)} transition-all duration-300`}
                style={{ width: `${stats.coverage_percentage}%` }}
              ></div>
            </div>

            {/* Statistics */}
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-gray-600">Present:</span>
                <span className="ml-2 font-medium">{stats.field_present.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-gray-600">Missing:</span>
                <span className="ml-2 font-medium text-red-600">{stats.missing_count.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-gray-600">Non-empty:</span>
                <span className="ml-2 font-medium">{stats.non_empty_values.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-gray-600">Empty:</span>
                <span className="ml-2 font-medium text-orange-600">{stats.empty_count.toLocaleString()}</span>
              </div>
            </div>

            {/* Sample Values (Expanded View) */}
            {selectedField === fieldName && (
              <div className="mt-4 pt-4 border-t border-gray-200">
                <h5 className="text-sm font-medium text-gray-700 mb-2">Sample Values:</h5>
                <div className="space-y-1">
                  {stats.sample_values.map((value: string, index: number) => (
                    <div key={index} className="text-xs bg-gray-100 px-2 py-1 rounded">
                      {value.length > 50 ? `${value.substring(0, 50)}...` : value}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Last Updated */}
      <div className="mt-6 text-center text-sm text-gray-500">
        Last updated: {fieldStats?.timestamp ? new Date(fieldStats.timestamp).toLocaleString() : 'Unknown'}
      </div>
    </div>
  );
};

export default FieldStatistics;
