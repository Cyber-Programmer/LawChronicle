import React, { useState, useEffect } from 'react';
import ProcessingButton from '../common/ProcessingButton';
import { Play, Settings } from 'lucide-react';
import { Phase5ApiService } from './apiService';
import type { StartGroupingRequest, Phase5Status } from './types';

interface StartGroupingButtonProps {
  disabled?: boolean;
  status: Phase5Status;
  onGroupingStarted: (taskId: string, totalStatutes: number) => void;
  onError: (error: string) => void;
  onCollectionChanged?: (collection: string) => void;
}

interface GroupingConfig {
  selectedCollection: string;
  similarityThreshold: number;
  batchSize: number;
  useAzureOpenAI: boolean;
}

export default function StartGroupingButton({ 
  disabled, 
  status, 
  onGroupingStarted, 
  onError,
  onCollectionChanged
}: StartGroupingButtonProps) {
  const [isStarting, setIsStarting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [availableCollections, setAvailableCollections] = useState<string[]>([]);
  const [config, setConfig] = useState<GroupingConfig>({
    selectedCollection: '',
    similarityThreshold: 0.85,
    batchSize: 50,
    useAzureOpenAI: true,
  });

  // Load available collections on mount
  useEffect(() => {
    const loadCollections = async () => {
      try {
        const response = await Phase5ApiService.getCollections();
        setAvailableCollections(response.collections);
        
        // Auto-select first collection if available
        if (response.collections.length > 0 && !config.selectedCollection) {
          const firstCollection = response.collections[0];
          setConfig(prev => ({ ...prev, selectedCollection: firstCollection }));
          // Notify parent about auto-selection
          if (onCollectionChanged) {
            onCollectionChanged(firstCollection);
          }
        }
      } catch (error) {
        console.error('Failed to load collections:', error);
        onError('Failed to load available collections');
      }
    };

    loadCollections();
  }, [onError, onCollectionChanged, config.selectedCollection]);

  const isDisabled = disabled || isStarting || status?.is_processing || !config.selectedCollection;

  const handleStartGrouping = async () => {
    try {
      setIsStarting(true);

      const request: StartGroupingRequest = {
        config: {
          similarity_threshold: config.similarityThreshold,
          batch_size: config.batchSize,
          use_azure_openai: config.useAzureOpenAI,
        },
        // Send single collection as array
        source_collections: config.selectedCollection ? [config.selectedCollection] : undefined,
      };

      const response = await Phase5ApiService.startGrouping(request);
      
      if (response && response.success) {
        onGroupingStarted(
          response.task_id || 'unknown', 
          response.total_statutes || 0
        );
      } else {
        onError(response?.message || 'Failed to start grouping process');
      }
    } catch (error) {
      console.error('Error starting grouping:', error);
      onError(error instanceof Error ? error.message : 'Unknown error occurred');
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <ProcessingButton
          onClick={handleStartGrouping}
          disabled={isDisabled}
          isProcessing={isStarting}
          icon={Play}
          progressText="Starting Grouping..."
          variant="primary"
          size="lg"
        >
          Start Statute Grouping
        </ProcessingButton>

        <ProcessingButton
          onClick={() => setShowAdvanced(!showAdvanced)}
          disabled={isDisabled}
          icon={Settings}
          variant="secondary"
          size="lg"
        >
          Advanced
        </ProcessingButton>
      </div>

      {/* Collection Selection */}
      <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-blue-900">Collection Selection</h3>
          <span className="text-xs text-blue-600">
            {availableCollections.length} collections available
          </span>
        </div>
        
        <div>
          <label className="block text-xs font-medium text-blue-700 mb-2">
            Select Collection to Process
          </label>
          <select
            value={config.selectedCollection}
            onChange={(e) => {
              const newCollection = e.target.value;
              setConfig(prev => ({ ...prev, selectedCollection: newCollection }));
              // Notify parent about collection change
              if (onCollectionChanged) {
                onCollectionChanged(newCollection);
              }
            }}
            className="w-full px-3 py-2 border border-blue-300 rounded-md text-sm bg-white"
            disabled={isDisabled}
          >
            <option value="">Select a collection...</option>
            {availableCollections.map((collection) => (
              <option key={collection} value={collection}>
                {collection}
              </option>
            ))}
          </select>
          <p className="text-xs text-blue-600 mt-1">
            Process one collection at a time (following Phase 4 pattern)
          </p>
        </div>
      </div>

      {showAdvanced && (
        <div className="bg-gray-50 p-4 rounded-lg border space-y-4">
          <h3 className="text-sm font-medium text-gray-900">Advanced Configuration</h3>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Similarity Threshold
              </label>
              <input
                type="number"
                min="0.1"
                max="1.0"
                step="0.05"
                value={config.similarityThreshold}
                onChange={(e) => setConfig(prev => ({
                  ...prev,
                  similarityThreshold: parseFloat(e.target.value)
                }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                disabled={isDisabled}
              />
              <p className="text-xs text-gray-500 mt-1">
                Higher values = stricter grouping (0.1-1.0)
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Batch Size
              </label>
              <input
                type="number"
                min="10"
                max="200"
                step="10"
                value={config.batchSize}
                onChange={(e) => setConfig(prev => ({
                  ...prev,
                  batchSize: parseInt(e.target.value)
                }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                disabled={isDisabled}
              />
              <p className="text-xs text-gray-500 mt-1">
                Statutes processed per batch (10-200)
              </p>
            </div>
          </div>

          <div className="flex items-center">
            <input
              id="use-azure-openai"
              type="checkbox"
              checked={config.useAzureOpenAI}
              onChange={(e) => setConfig(prev => ({
                ...prev,
                useAzureOpenAI: e.target.checked
              }))}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              disabled={isDisabled}
            />
            <label htmlFor="use-azure-openai" className="ml-2 block text-sm text-gray-900">
              Use Azure OpenAI for semantic grouping
            </label>
          </div>
          
          {!status?.azure_openai_configured && config.useAzureOpenAI && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
              <p className="text-sm text-yellow-800">
                ⚠️ Azure OpenAI is not configured. Grouping will use fallback similarity matching.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Status Information */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-blue-900 mb-2">Current Status</h4>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="font-medium text-blue-700">Source Database:</span>
            <span className="ml-2 text-blue-600">{status?.source_database || 'N/A'}</span>
          </div>
          <div>
            <span className="font-medium text-blue-700">Target Database:</span>
            <span className="ml-2 text-blue-600">{status?.target_database || 'N/A'}</span>
          </div>
          <div>
            <span className="font-medium text-blue-700">Collections:</span>
            <span className="ml-2 text-blue-600">{status?.source_collections || '0'}</span>
          </div>
          <div>
            <span className="font-medium text-blue-700">Total Statutes:</span>
            <span className="ml-2 text-blue-600">{status.total_source_documents?.toLocaleString() || '0'}</span>
          </div>
          <div>
            <span className="font-medium text-blue-700">Azure OpenAI:</span>
            <span className={`ml-2 ${status?.azure_openai_configured ? 'text-green-600' : 'text-red-600'}`}>
              {status?.azure_openai_configured ? '✓ Configured' : '✗ Not Configured'}
            </span>
          </div>
          <div>
            <span className="font-medium text-blue-700">Model:</span>
            <span className="ml-2 text-blue-600">{status?.deployment_name || 'N/A'}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
