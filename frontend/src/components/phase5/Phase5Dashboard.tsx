import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AlertCircle, CheckCircle2, BarChart3, Settings, RefreshCw } from 'lucide-react';
import StartGroupingButton from './StartGroupingButton';
import ProgressStream from './ProgressStream';
import GroupedStatutesViewer from './GroupedStatutesViewer';
import { Phase5ApiService } from './apiService';
import type { Phase5Status } from './types';

export default function Phase5Dashboard() {
  const [status, setStatus] = useState<Phase5Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [stats, setStats] = useState<any>(null);
  const [selectedCollection, setSelectedCollection] = useState<string>('');

  // Component lifecycle and request tracking refs
  const isMountedRef = useRef(true);
  const loadingRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastRequestRef = useRef<string>('');

  // Cleanup function
  const cleanup = useCallback(() => {
    console.log('Phase5Dashboard: Cleaning up...');
    isMountedRef.current = false;
    loadingRef.current = false;
    lastRequestRef.current = '';
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  // Memoized loadStatus function with proper dependencies and deduplication
  const loadStatus = useCallback(async (collection?: string, options: { skipLoading?: boolean, force?: boolean } = {}) => {
    const { skipLoading = false, force = false } = options;
    
    // Use passed collection or the currently selected one
    const collectionToUse = collection || selectedCollection;
    const requestKey = `loadStatus-${collectionToUse}`;
    
    // Prevent overlapping requests unless forced
    if (!force && loadingRef.current) {
      console.log('LoadStatus: Request already in progress, skipping');
      return;
    }

    // Prevent duplicate requests within short timeframe
    if (!force && lastRequestRef.current === requestKey) {
      console.log('LoadStatus: Duplicate request detected, skipping');
      return;
    }

    try {
      // Set loading flags
      loadingRef.current = true;
      lastRequestRef.current = requestKey;
      
      if (!skipLoading && isMountedRef.current) {
        setLoading(true);
      }
      
      // Cancel previous request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      
      // Create new abort controller
      abortControllerRef.current = new AbortController();
      const signal = abortControllerRef.current.signal;

      // Clear error if this is a retry
      if (error && isMountedRef.current) {
        setError(null);
      }
      
      console.log(`LoadStatus: Fetching status for collection: ${collectionToUse || 'default'}`);
      
      // Fetch status with abort signal
      const statusResponse = await Phase5ApiService.getStatus(collectionToUse || undefined);
      
      // Check if component is still mounted and request wasn't aborted
      if (!isMountedRef.current || signal.aborted) {
        console.log('LoadStatus: Component unmounted or request aborted');
        return;
      }

      // Batch state updates for status
      if (statusResponse) {
        const isCurrentlyProcessing = statusResponse.is_processing || false;
        
        // Update all related state in a batch
        if (isMountedRef.current) {
          setStatus(statusResponse);
          setIsProcessing(isCurrentlyProcessing);
        }

        // Load statistics if groups exist and component is still mounted
        if (statusResponse.grouped_documents && statusResponse.grouped_documents > 0 && isMountedRef.current) {
          try {
            console.log('LoadStatus: Loading statistics...');
            const statsResponse = await Phase5ApiService.getStatistics();
            
            if (isMountedRef.current && !signal.aborted) {
              setStats(statsResponse);
            }
          } catch (statsError: any) {
            // Only log stats errors, don't set error state for optional stats
            if (!signal.aborted) {
              console.error('Failed to load statistics:', statsError);
            }
          }
        }
      } else {
        if (isMountedRef.current) {
          setError('Invalid response from Phase 5 service');
        }
      }
    } catch (err: any) {
      // Don't set error state if request was aborted or component unmounted
      if (!abortControllerRef.current?.signal.aborted && isMountedRef.current) {
        console.error('Error loading status:', err);
        const errorMessage = err instanceof Error ? err.message : 'Failed to load Phase 5 status. Service may not be available.';
        
        // Batch error state updates
        setError(errorMessage);
        
        // Set fallback status to prevent complete failure
        setStatus({
          current_phase: 'phase5',
          status: 'unknown',
          is_processing: false,
          source_database: 'N/A',
          target_database: 'N/A',
          source_collections: 0,
          total_source_documents: 0,
          grouped_documents: 0,
          azure_openai_configured: false,
          deployment_name: 'N/A',
          current_progress: 0
        });
      }
    } finally {
      // Clear loading flags
      loadingRef.current = false;
      
      // Clear request tracking after delay to prevent immediate duplicates
      setTimeout(() => {
        if (lastRequestRef.current === requestKey) {
          lastRequestRef.current = '';
        }
      }, 1000);
      
      if (!skipLoading && isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [selectedCollection, error]);

  // Memoized grouping started handler
  const handleGroupingStarted = useCallback((taskId: string, totalStatutes: number) => {
    console.log(`Grouping started - Task ID: ${taskId}, Total Statutes: ${totalStatutes}`);
    if (isMountedRef.current) {
      setIsProcessing(true);
      setError(null);
      // Refresh status to show updated state with a delay
      setTimeout(() => {
        if (isMountedRef.current) {
          loadStatus(undefined, { skipLoading: false, force: true });
        }
      }, 1000);
    }
  }, [loadStatus]);

  // Memoized grouping completion handler
  const handleGroupingComplete = useCallback(() => {
    console.log('Grouping completed, updating state...');
    if (isMountedRef.current) {
      setIsProcessing(false);
      setRefreshTrigger(prev => prev + 1);
      // Force reload with slight delay to ensure backend state is consistent
      setTimeout(() => {
        if (isMountedRef.current) {
          loadStatus(undefined, { skipLoading: false, force: true });
        }
      }, 500);
    }
  }, [loadStatus]);

  // Memoized error handler
  const handleError = useCallback((errorMessage: string) => {
    console.log('Error occurred, updating state:', errorMessage);
    if (isMountedRef.current) {
      setError(errorMessage);
      setIsProcessing(false);
      // Refresh status to check current state
      loadStatus(undefined, { skipLoading: false, force: true });
    }
  }, [loadStatus]);

  // Memoized clear data handler
  const handleClearData = useCallback(async () => {
    if (!window.confirm('Are you sure you want to clear all grouping data? This action cannot be undone.')) {
      return;
    }

    try {
      await Phase5ApiService.clearGroups();
      if (isMountedRef.current) {
        setRefreshTrigger(prev => prev + 1);
        setStats(null);
        loadStatus(undefined, { skipLoading: false, force: true });
      }
    } catch (err) {
      console.error('Error clearing data:', err);
      if (isMountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to clear data');
      }
    }
  }, [loadStatus]);

  // Initial load effect with proper cleanup
  useEffect(() => {
    isMountedRef.current = true;
    
    // Initial load
    loadStatus(undefined, { skipLoading: false, force: true });
    
    // Return cleanup function
    return cleanup;
  }, [loadStatus, cleanup]); // Include dependencies

  // Handle collection changes with separate effect
  useEffect(() => {
    // Skip initial mount (handled by the initial effect above)
    if (isMountedRef.current && selectedCollection) {
      console.log(`Collection changed to: ${selectedCollection}, reloading status...`);
      loadStatus(selectedCollection, { skipLoading: false, force: true });
    }
  }, [selectedCollection, loadStatus]); // Depend on selectedCollection and memoized loadStatus

  // Handle refresh triggers (when refreshTrigger changes)
  useEffect(() => {
    if (isMountedRef.current && refreshTrigger > 0) {
      console.log(`Refresh triggered (${refreshTrigger}), reloading status...`);
      loadStatus(undefined, { skipLoading: false, force: true });
    }
  }, [refreshTrigger, loadStatus]); // Depend on refreshTrigger and memoized loadStatus

  // Memoized collection change handler
  const handleCollectionChanged = useCallback((collection: string) => {
    console.log(`Collection changed to: ${collection}, updating state...`);
    setSelectedCollection(collection);
    // The useEffect above will handle the actual loading
  }, []);

  // Memoized refresh handler
  const handleRefreshClick = useCallback(() => {
    console.log('Manual refresh requested, forcing reload...');
    loadStatus(undefined, { skipLoading: false, force: true });
  }, [loadStatus]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="bg-white rounded-lg shadow p-8">
            <div className="flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
              <span className="ml-3 text-gray-600">Loading Phase 5 Dashboard...</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error && !status) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="bg-white rounded-lg shadow p-8">
            <div className="text-center">
              <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Error Loading Dashboard</h2>
              <p className="text-gray-600 mb-6">{error}</p>
              <button
                onClick={handleRefreshClick}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Phase 5: Statute Grouping & Versioning
              </h1>
              <p className="text-gray-600 mt-2">
                Semantic grouping and chronological versioning of legal statutes using AI
              </p>
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={handleRefreshClick}
                className="flex items-center px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
              >
                <RefreshCw className="h-4 w-4 mr-1" />
                Refresh
              </button>
              {status && status.grouped_documents && status.grouped_documents > 0 && (
                <button
                  onClick={handleClearData}
                  className="flex items-center px-3 py-2 text-sm border border-red-300 text-red-700 rounded-md hover:bg-red-50"
                >
                  <Settings className="h-4 w-4 mr-1" />
                  Clear Data
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-start">
              <AlertCircle className="h-5 w-5 text-red-400 mt-0.5 mr-3 flex-shrink-0" />
              <div>
                <h3 className="text-sm font-medium text-red-800">Error</h3>
                <p className="text-sm text-red-700 mt-1">{error}</p>
                <button
                  onClick={() => setError(null)}
                  className="text-sm text-red-600 underline mt-2 hover:text-red-800"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Statistics Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <BarChart3 className="h-8 w-8 text-blue-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Total Groups</p>
                  <p className="text-2xl font-bold text-gray-900">{stats?.total_groups?.toLocaleString() || '0'}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <CheckCircle2 className="h-8 w-8 text-green-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Total Statutes</p>
                  <p className="text-2xl font-bold text-gray-900">{stats?.total_statutes?.toLocaleString() || '0'}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <BarChart3 className="h-8 w-8 text-purple-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Avg Versions</p>
                  <p className="text-2xl font-bold text-gray-900">{stats?.average_versions_per_group?.toFixed(1) || '0.0'}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <Settings className="h-8 w-8 text-orange-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Most Common Province</p>
                  <p className="text-lg font-bold text-gray-900">
                    {Object.entries(stats.groups_by_province || {})
                      .sort(([,a], [,b]) => (b as number) - (a as number))[0]?.[0] || 'N/A'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Controls */}
          <div className="lg:col-span-1 space-y-6">
            {/* Start Grouping */}
            {status && (
              <StartGroupingButton
                status={status}
                disabled={isProcessing}
                onGroupingStarted={handleGroupingStarted}
                onError={handleError}
                onCollectionChanged={handleCollectionChanged}
              />
            )}

            {/* Progress Stream */}
            <ProgressStream
              isActive={isProcessing}
              onComplete={handleGroupingComplete}
              onError={handleError}
            />
          </div>

          {/* Right Column - Results */}
          <div className="lg:col-span-2">
            <GroupedStatutesViewer refreshTrigger={refreshTrigger} />
          </div>
        </div>

        {/* Province Distribution Chart */}
        {stats && stats.groups_by_province && Object.keys(stats.groups_by_province).length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Groups by Province</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
              {Object.entries(stats.groups_by_province)
                .sort(([,a], [,b]) => (b as number) - (a as number))
                .map(([province, count]) => (
                  <div key={province} className="text-center">
                    <div className="text-2xl font-bold text-blue-600">{count as number}</div>
                    <div className="text-sm text-gray-600">{province}</div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Status Footer */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between text-sm text-gray-600">
            <div className="flex items-center space-x-4">
              <span>Phase: {status?.current_phase}</span>
              <span>Status: {status?.status}</span>
              {status?.azure_openai_configured && (
                <span className="text-green-600">✓ Azure OpenAI</span>
              )}
            </div>
            <div>
              Last updated: {new Date().toLocaleTimeString()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
