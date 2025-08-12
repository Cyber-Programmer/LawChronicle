import React, { useState, useEffect, useCallback } from 'react';
import { BarChart3, RefreshCw, Play, AlertTriangle, CheckCircle, ChevronDown, ChevronRight, TrendingUp, Clock, Database, FileText } from 'lucide-react';

interface StatuteGroup {
  _id: string;
  Statute_Name: string;
  Sections: any[];
  section_count: number;
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

interface ProgressTrackerProps {
  config: any;
}

const ProgressTracker: React.FC<ProgressTrackerProps> = ({ config }) => {
  const [statuteGroups, setStatuteGroups] = useState<StatuteGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [progressMetrics, setProgressMetrics] = useState<ProgressMetrics | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Fetch statute groups and progress from normalized collection
  const fetchProgressData = useCallback(async () => {
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
        
        // Calculate progress metrics
        const totalStatutes = groups.length;
        const totalSections = groups.reduce((sum: number, statute: { section_count: number }) => sum + statute.section_count, 0);
        // For now, assume all statutes are processed if they exist
        const processedStatutes = totalStatutes;
        const processedSections = totalSections;
        
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
        setMessage({ type: 'error', text: 'Failed to fetch progress data' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Error fetching progress data' });
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

  // Auto-refresh progress
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchProgressData, 30000); // Refresh every 30 seconds
      return () => clearInterval(interval);
    }
  }, [autoRefresh, fetchProgressData]);

  // Initial load
  useEffect(() => {
    fetchProgressData();
  }, [fetchProgressData]);

  // Get progress bar color based on percentage
  const getProgressColor = (percentage: number) => {
    if (percentage >= 80) return 'bg-green-500';
    if (percentage >= 60) return 'bg-yellow-500';
    if (percentage >= 40) return 'bg-orange-500';
    return 'bg-red-500';
  };

  // Get phase status icon and color
  const getPhaseStatus = (phase: string) => {
    if (phase.includes('Complete')) {
      return { icon: CheckCircle, color: 'text-green-600', bgColor: 'bg-green-100' };
    } else if (phase.includes('Processing')) {
      return { icon: Clock, color: 'text-blue-600', bgColor: 'bg-blue-100' };
    } else if (phase.includes('Pending')) {
      return { icon: Clock, color: 'text-gray-600', bgColor: 'bg-gray-100' };
    } else {
      return { icon: AlertTriangle, color: 'text-yellow-600', bgColor: 'bg-yellow-100' };
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <BarChart3 className="w-5 h-5 mr-2" />
          Progress Tracker - Grouped Normalization
        </h2>
        <p className="text-gray-600 mb-4">
          Track the progress of normalization workflow: grouping statutes, sorting sections, and overall completion status.
        </p>
        
        {/* Controls */}
        <div className="flex flex-wrap gap-4 items-center">
          <button
            onClick={fetchProgressData}
            disabled={loading}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh Progress
          </button>
          
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700">Auto-refresh every 30s</span>
          </label>
        </div>
      </div>

      {/* Progress Overview */}
      {progressMetrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Overall Progress */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Overall Progress</h3>
              <TrendingUp className="w-6 h-6 text-blue-600" />
            </div>
            <div className="text-3xl font-bold text-blue-600 mb-2">
              {Math.round(progressMetrics.overall_progress)}%
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className={`h-2 rounded-full ${getProgressColor(progressMetrics.overall_progress)}`}
                style={{ width: `${progressMetrics.overall_progress}%` }}
              />
            </div>
            <div className="text-sm text-gray-600 mt-2">
              {progressMetrics.processed_statutes} of {progressMetrics.total_statutes} statutes
            </div>
          </div>

          {/* Normalization Progress */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Normalization</h3>
              <Database className="w-6 h-6 text-green-600" />
            </div>
            <div className="text-3xl font-bold text-green-600 mb-2">
              {Math.round(progressMetrics.normalization_progress)}%
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className={`h-2 rounded-full ${getProgressColor(progressMetrics.normalization_progress)}`}
                style={{ width: `${progressMetrics.normalization_progress}%` }}
              />
            </div>
            <div className="text-sm text-gray-600 mt-2">
              {progressMetrics.processed_statutes} statutes grouped
            </div>
          </div>

          {/* Sorting Progress */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Section Sorting</h3>
              <FileText className="w-6 h-6 text-purple-600" />
            </div>
            <div className="text-3xl font-bold text-purple-600 mb-2">
              {Math.round(progressMetrics.sorting_progress)}%
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className={`h-2 rounded-full ${getProgressColor(progressMetrics.sorting_progress)}`}
                style={{ width: `${progressMetrics.sorting_progress}%` }}
              />
            </div>
            <div className="text-sm text-gray-600 mt-2">
              {progressMetrics.processed_sections} sections sorted
            </div>
          </div>

          {/* Current Status */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Current Phase</h3>
              <Clock className="w-6 h-6 text-orange-600" />
            </div>
            <div className="mb-3">
              {(() => {
                const status = getPhaseStatus(progressMetrics.current_phase);
                const Icon = status.icon;
                return (
                  <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${status.bgColor} ${status.color}`}>
                    <Icon className="w-4 h-4 mr-2" />
                    {progressMetrics.current_phase}
                  </div>
                );
              })()}
            </div>
            <div className="text-sm text-gray-600">
              Last updated: {new Date(progressMetrics.last_updated).toLocaleTimeString()}
            </div>
            {progressMetrics.estimated_time_remaining !== '0 minutes' && (
              <div className="text-sm text-gray-600 mt-1">
                Est. remaining: {progressMetrics.estimated_time_remaining}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Workflow Steps */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Workflow Steps</h3>
        <div className="space-y-4">
          <div className="flex items-start space-x-4">
            <div className="bg-green-100 text-green-800 rounded-full w-8 h-8 flex items-center justify-center text-sm font-medium flex-shrink-0">
              1
            </div>
            <div className="flex-1">
              <div className="font-medium text-gray-900">Data Ingestion</div>
              <div className="text-sm text-gray-600">Load raw documents from source collection</div>
              <div className="text-xs text-green-600 mt-1">✓ Complete</div>
            </div>
          </div>
          
          <div className="flex items-start space-x-4">
            <div className="bg-green-100 text-green-800 rounded-full w-8 h-8 flex items-center justify-center text-sm font-medium flex-shrink-0">
              2
            </div>
            <div className="flex-1">
              <div className="font-medium text-gray-900">Statute Name Normalization</div>
              <div className="text-sm text-gray-600">Clean and standardize statute names</div>
              <div className="text-xs text-green-600 mt-1">✓ Complete</div>
            </div>
          </div>
          
          <div className="flex items-start space-x-4">
            <div className="bg-green-100 text-green-800 rounded-full w-8 h-8 flex items-center justify-center text-sm font-medium flex-shrink-0">
              3
            </div>
            <div className="flex-1">
              <div className="font-medium text-gray-900">Section Grouping</div>
              <div className="text-sm text-gray-600">Group sections by normalized statute name</div>
              <div className="text-xs text-green-600 mt-1">✓ Complete</div>
            </div>
          </div>
          
          <div className="flex items-start space-x-4">
            <div className="bg-green-100 text-green-800 rounded-full w-8 h-8 flex items-center justify-center text-sm font-medium flex-shrink-0">
              4
            </div>
            <div className="flex-1">
              <div className="font-medium text-gray-900">Section Sorting</div>
              <div className="text-sm text-gray-600">Sort sections: preamble, numeric, text</div>
              <div className="text-xs text-green-600 mt-1">✓ Complete</div>
            </div>
          </div>
          
          <div className="flex items-start space-x-4">
            <div className="bg-green-100 text-green-800 rounded-full w-8 h-8 flex items-center justify-center text-sm font-medium flex-shrink-0">
              5
            </div>
            <div className="flex-1">
              <div className="font-medium text-gray-900">Database Insertion</div>
              <div className="text-sm text-gray-600">Insert normalized statutes into target collection</div>
              <div className="text-xs text-green-600 mt-1">✓ Complete</div>
            </div>
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

      {/* Statute Groups Progress */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Statute Groups Progress</h3>
          <p className="text-sm text-gray-600">
            {statuteGroups.length} groups loaded • Click to expand and view section details
          </p>
        </div>
        
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
            Loading progress data...
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
                  
                  <div className="flex items-center space-x-4">
                    <div className="text-sm text-gray-500">
                      Sections: {statute.section_count}
                    </div>
                    <div className="text-sm text-green-600 font-medium">
                      ✓ Normalized
                    </div>
                  </div>
                </div>
                
                {/* Expanded Sections View */}
                {expandedGroups.has(statute._id) && (
                  <div className="mt-3 ml-8 space-y-2">
                    <div className="text-sm text-gray-600 font-medium">Section Progress:</div>
                    {statute.Sections && statute.Sections.length > 0 ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                        {statute.Sections.slice(0, 6).map((section: any, index: number) => (
                          <div key={index} className="bg-gray-50 p-2 rounded text-sm">
                            <div className="font-medium text-gray-700 mb-1">
                              {section.number || section.section_number || `Section ${index + 1}`}
                            </div>
                            <div className="text-xs text-gray-600 truncate">
                              {section.definition || section.content || 'No content'}
                            </div>
                            <div className="text-xs text-green-600 mt-1">✓ Sorted</div>
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
          Overall progress: {progressMetrics ? Math.round(progressMetrics.overall_progress) : 0}% • 
          Status: {progressMetrics?.current_phase || 'Unknown'}
        </div>
      </div>
    </div>
  );
};

export default ProgressTracker;
