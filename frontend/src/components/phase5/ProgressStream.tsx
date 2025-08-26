import React, { useState, useEffect, useRef } from 'react';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { Phase5ApiService } from './apiService';
import type { GroupingProgress } from './types';

interface ProgressStreamProps {
  isActive: boolean;
  onComplete: () => void;
  onError: (error: string) => void;
}

export default function ProgressStream({ isActive, onComplete, onError }: ProgressStreamProps) {
  const [progress, setProgress] = useState<GroupingProgress | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!isActive) {
      // Clean up connection when not active
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        setIsConnected(false);
        setProgress(null);
      }
      return;
    }

    // Create new EventSource connection
    try {
      const eventSource = Phase5ApiService.createProgressStream();
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        console.log('Progress stream connected');
        setIsConnected(true);
      };

      eventSource.onmessage = (event) => {
        try {
          const progressData: GroupingProgress = JSON.parse(event.data);
          setProgress(progressData);

          // Handle completion
          if (progressData.status === 'completed') {
            setTimeout(() => {
              onComplete();
            }, 2000); // Show completed state for 2 seconds
          } else if (progressData.status === 'error') {
            onError(progressData.error || 'Unknown error occurred during grouping');
          }
        } catch (error) {
          console.error('Error parsing progress data:', error);
          onError('Failed to parse progress data');
        }
      };

      eventSource.onerror = (error) => {
        console.error('EventSource error:', error);
        setIsConnected(false);
        
        // Only report error if we're still supposed to be active
        if (isActive) {
          onError('Lost connection to progress stream');
        }
      };

    } catch (error) {
      console.error('Failed to create progress stream:', error);
      onError('Failed to connect to progress stream');
    }

    // Cleanup function
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        setIsConnected(false);
      }
    };
  }, [isActive, onComplete, onError]);

  if (!isActive) {
    return null;
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">Grouping Progress</h3>
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400'}`}></div>
          <span className="text-sm text-gray-500">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {progress && (
        <>
          {/* Progress Bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="font-medium text-gray-700">
                {getStatusLabel(progress.status)}
              </span>
              <span className="text-gray-500">
                {progress.progress.toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className={`h-2 rounded-full transition-all duration-300 ${getProgressBarColor(progress.status)}`}
                style={{ width: `${progress.progress}%` }}
              ></div>
            </div>
          </div>

          {/* Status Message */}
          <div className="flex items-start space-x-3">
            {getStatusIcon(progress.status)}
            <div className="flex-1">
              <p className="text-sm text-gray-700">{progress.message}</p>
              {progress.timestamp && (
                <p className="text-xs text-gray-500 mt-1">
                  {new Date(progress.timestamp).toLocaleTimeString()}
                </p>
              )}
            </div>
          </div>

          {/* Statistics */}
          {(progress.total_statutes || progress.total_groups || progress.total_versioned) && (
            <div className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-100">
              {progress.total_statutes && (
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {progress.total_statutes.toLocaleString()}
                  </div>
                  <div className="text-xs text-gray-500">Total Statutes</div>
                </div>
              )}
              {progress.total_groups && (
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {progress.total_groups.toLocaleString()}
                  </div>
                  <div className="text-xs text-gray-500">Groups Created</div>
                </div>
              )}
              {progress.total_versioned && (
                <div className="text-center">
                  <div className="text-2xl font-bold text-purple-600">
                    {progress.total_versioned.toLocaleString()}
                  </div>
                  <div className="text-xs text-gray-500">Versions Assigned</div>
                </div>
              )}
            </div>
          )}

          {/* Error Display */}
          {progress.error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3">
              <div className="flex items-start">
                <AlertCircle className="h-5 w-5 text-red-400 mt-0.5 mr-2 flex-shrink-0" />
                <div>
                  <h4 className="text-sm font-medium text-red-800">Error</h4>
                  <p className="text-sm text-red-700 mt-1">{progress.error}</p>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {!progress && isConnected && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-blue-500 mr-2" />
          <span className="text-gray-500">Waiting for progress updates...</span>
        </div>
      )}
    </div>
  );
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'fetching': return 'Fetching Statutes';
    case 'fetching_complete': return 'Fetching Complete';
    case 'grouping': return 'Grouping Statutes';
    case 'grouping_complete': return 'Grouping Complete';
    case 'versioning': return 'Assigning Versions';
    case 'completed': return 'Process Complete';
    case 'error': return 'Error';
    default: return 'Processing';
  }
}

function getProgressBarColor(status: string): string {
  switch (status) {
    case 'completed': return 'bg-green-500';
    case 'error': return 'bg-red-500';
    case 'grouping': return 'bg-blue-500';
    case 'versioning': return 'bg-purple-500';
    default: return 'bg-blue-500';
  }
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />;
    case 'error':
      return <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />;
    default:
      return <Loader2 className="h-5 w-5 animate-spin text-blue-500 flex-shrink-0" />;
  }
}
