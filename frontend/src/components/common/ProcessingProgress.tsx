import React from 'react';
import { Loader2, AlertCircle, CheckCircle } from 'lucide-react';

export interface ProcessingStats {
  processed: number;
  total: number;
  operation: string;
}

interface ProcessingProgressProps {
  isProcessing: boolean;
  progressStep?: string;
  progressDetails?: string;
  processingStats?: ProcessingStats | null;
  error?: string | null;
  onDismissError?: () => void;
  variant?: 'default' | 'compact';
}

const ProcessingProgress: React.FC<ProcessingProgressProps> = ({
  isProcessing,
  progressStep,
  progressDetails,
  processingStats,
  error,
  onDismissError,
  variant = 'default'
}) => {
  const isComplete = !isProcessing && !error && progressStep && progressStep.includes('completed');

  if (variant === 'compact') {
    return (
      <>
        {isProcessing && (
          <div className="flex items-center space-x-2 text-sm">
            <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
            <span className="text-blue-700">{progressStep || 'Processing...'}</span>
          </div>
        )}
        {error && (
          <div className="flex items-center space-x-2 text-sm text-red-600">
            <AlertCircle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}
      </>
    );
  }

  return (
    <div className="space-y-4">
      {/* Processing Status */}
      {isProcessing && (
        <div className="bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Processing Status</h3>
            <div className="flex items-center">
              <Loader2 className="w-5 h-5 text-blue-600 animate-spin mr-2" />
              <span className="text-sm font-medium text-blue-700">In Progress</span>
            </div>
          </div>
          
          {progressStep && (
            <div className="mb-3">
              <div className="text-base font-medium text-gray-800 mb-1">
                {progressStep}
              </div>
              {progressDetails && (
                <div className="text-sm text-gray-600">
                  {progressDetails}
                </div>
              )}
            </div>
          )}
          
          {processingStats && (
            <div className="bg-white rounded-lg p-4 border border-gray-200">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium text-gray-700">{processingStats.operation}</span>
                <span className="text-sm text-gray-600">
                  {processingStats.processed.toLocaleString()} processed
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div 
                  className="bg-gradient-to-r from-blue-500 to-purple-600 h-3 rounded-full transition-all duration-500 ease-out" 
                  style={{ width: `${Math.min((processingStats.processed / processingStats.total) * 100, 100)}%` }}
                ></div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Completion Status */}
      {isComplete && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center">
            <CheckCircle className="w-5 h-5 text-green-600 mr-3" />
            <div>
              <div className="text-base font-medium text-green-900">{progressStep}</div>
              {progressDetails && (
                <div className="text-sm text-green-700">{progressDetails}</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-red-600 mr-3 mt-0.5" />
            <div className="flex-1">
              <h3 className="text-base font-medium text-red-900 mb-2">Operation Failed</h3>
              <div className="text-sm text-red-800 mb-3">{error}</div>
              <div className="text-xs text-red-600">
                <strong>Troubleshooting Steps:</strong>
                <ul className="mt-2 ml-4 list-disc space-y-1">
                  <li>Verify database connection is active</li>
                  <li>Check that source collections contain data</li>
                  <li>Ensure sufficient permissions for target database</li>
                  <li>Review configuration settings for accuracy</li>
                  <li>Try refreshing the page and attempting the operation again</li>
                </ul>
              </div>
              {onDismissError && (
                <button
                  onClick={onDismissError}
                  className="mt-3 text-sm text-red-600 hover:text-red-800 underline"
                >
                  Dismiss error
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProcessingProgress;
