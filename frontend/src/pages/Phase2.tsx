import React, { useState } from 'react';
import { Database, Play, Eye, RotateCcw, FileText, BarChart3, CheckCircle, AlertCircle, Loader2, Settings } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import StatuteNameNormalizer from '../components/phase2/StatuteNameNormalizer';
import ResultsPreview from '../components/phase2/ResultsPreview';

interface NormalizationResult {
  success: boolean;
  message: string;
  metadata?: any;
  summary?: any;
  completed_at?: string;
}

interface PreviewData {
  success: boolean;
  message: string;
  total_statutes?: number;
  unique_statutes_found?: number;
  total_raw_documents?: number;
  preview_data?: any[];
  data_structure?: any;
}

interface NormalizationConfig {
  source_collection: string;
  target_collection: string;
  database_name?: string;
  sorted_collection: string;
}

type TabType = 'overview' | 'statute-names' | 'results';

const Phase2: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [isNormalizing, setIsNormalizing] = useState(false);
  const [saveMetadata, setSaveMetadata] = useState(false);
  const [normalizationResult, setNormalizationResult] = useState<NormalizationResult | null>(null);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [statusInfo, setStatusInfo] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [progressStep, setProgressStep] = useState<string>('');
  const [progressDetails, setProgressDetails] = useState<string>('');
  const [processingStats, setProcessingStats] = useState<{processed: number, total: number} | null>(null);
  
  // Configuration state
  const [config, setConfig] = useState<NormalizationConfig>({
    source_collection: "raw_statutes",
    target_collection: "normalized_statutes",
    database_name: "Statutes",
    sorted_collection: "sorted_statutes"
  });

  const executeNormalization = async () => {
    setIsNormalizing(true);
    setError(null);
    setNormalizationResult(null);
    setProgressStep('Initializing normalization process...');
    setProgressDetails('Preparing service request and validating configuration');
    setProcessingStats(null);

    try {
      // Step 1: Prepare service request
      setProgressStep('Preparing normalization request');
      setProgressDetails(`Source: ${config.source_collection} → Target: ${config.target_collection}`);
      
      const sourceDb = config.database_name || "Statutes";
      const targetDb = config.database_name || "Statutes";
      
      const serviceRequest = {
        source_db: sourceDb,
        target_db: targetDb,
        options: {
          source_collection: config.source_collection,
          target_collection: config.target_collection,
          sorted_collection: config.sorted_collection,
          save_metadata: saveMetadata,
          batch_size: 1000,
          legacy_compatibility: true,  // Enable legacy mode
          same_database_mode: true,    // Allow same database
          actual_database: sourceDb    // The actual database name
        }
      };

      // Step 2: Send request to service
      setProgressStep('Sending request to normalization service');
      setProgressDetails('Connecting to backend service endpoint...');

            const response = await fetch('/api/v1/phase2/start-normalization', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(serviceRequest)
      });

      // Step 3: Process response
      setProgressStep('Processing service response');
      setProgressDetails('Analyzing normalization results...');

      const result = await response.json();
      
      if (response.ok) {
        // Step 4: Success handling
        setProgressStep('Normalization completed successfully!');
        setProgressDetails(`Processed statutes and created normalized collection`);
        
        // Transform service response to match expected format
        const transformedResult = {
          success: result.success,
          message: result.message,
          metadata: result.data?.metadata || result.data || {},
          timestamp: result.timestamp,
          service_based: true,
          migration_note: "Using modern service-based normalization"
        };
        setNormalizationResult(transformedResult);
        
        // Step 5: Refresh status
        setProgressStep('Refreshing status dashboard');
        setProgressDetails('Updating progress indicators...');
        await getNormalizationStatus();
        
        setProgressStep('Ready for next phase');
        setProgressDetails('Normalization completed successfully - ready to proceed');
      } else {
        throw new Error(result.detail?.message || result.message || 'Normalization failed');
      }
    } catch (err) {
      setProgressStep('Error occurred during normalization');
      setProgressDetails(err instanceof Error ? err.message : 'An unexpected error occurred');
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      setIsNormalizing(false);
      // Clear progress after a delay
      setTimeout(() => {
        if (!isNormalizing) {
          setProgressStep('');
          setProgressDetails('');
          setProcessingStats(null);
        }
      }, 3000);
    }
  };

  const getNormalizationStatus = async () => {
    try {
      const response = await fetch('/api/v1/phase2/normalization-status', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(config)
      });
      
      if (response.ok) {
        const status = await response.json();
        setStatusInfo(status);
      }
    } catch (err) {
      console.error('Failed to get status:', err);
    }
  };

  const previewNormalizedStructure = async () => {
    try {
      // First try the source-based preview (shows what will be normalized)
      const sourceResponse = await fetch('/api/v1/phase2/preview-source-normalization', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(config)
      });
      
      if (sourceResponse.ok) {
        const sourcePreview = await sourceResponse.json();
        setPreviewData(sourcePreview);
        return;
      }
      
      // Fallback to existing normalized data preview
      const response = await fetch('/api/v1/phase2/preview-normalized-structure?limit=5', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(config)
      });
      
      if (response.ok) {
        const preview = await response.json();
        setPreviewData(preview);
      } else {
        setError('Failed to preview structure - no source or normalized data available');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to preview data');
    }
  };

  const rollbackNormalization = async () => {
    if (!window.confirm('Are you sure you want to rollback the normalization? This will delete all normalized data.')) {
      return;
    }

    try {
      const response = await fetch('/api/v1/phase2/rollback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(config)
      });

      if (response.ok) {
        setNormalizationResult(null);
        setPreviewData(null);
        await getNormalizationStatus();
        setError(null);
      } else {
        const result = await response.json();
        setError(result.detail?.message || result.message || 'Rollback failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rollback failed');
    }
  };

  const handleConfigChange = (field: keyof NormalizationConfig, value: string) => {
    setConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const resetConfig = () => {
    setConfig({
      source_collection: "raw_statutes",
      target_collection: "normalized_statutes",
      database_name: "Statutes",
      sorted_collection: "sorted_statutes"
    });
  };

  React.useEffect(() => {
    getNormalizationStatus();
  }, []);

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Database },
    { id: 'statute-names', label: 'Statute Name Normalizer', icon: FileText },
    { id: 'results', label: 'Results Preview', icon: Eye }
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <div className="space-y-6">
            {/* Status Overview */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <BarChart3 className="w-5 h-5 mr-2" />
                Normalization Status
              </h3>
              {statusInfo ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-blue-600">{statusInfo.raw_count?.toLocaleString() || 0}</div>
                    <div className="text-sm text-blue-600">Raw Documents</div>
                  </div>
                  <div className="bg-green-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-green-600">{statusInfo.normalized_count?.toLocaleString() || 0}</div>
                    <div className="text-sm text-green-600">Normalized Statutes</div>
                  </div>
                  <div className="bg-purple-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-purple-600">{statusInfo.unique_statutes?.toLocaleString() || 0}</div>
                    <div className="text-sm text-purple-600">Unique Statutes</div>
                  </div>
                </div>
              ) : (
                <div className="text-gray-500">Loading status...</div>
              )}
            </div>

            {/* Configuration Panel */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <Settings className="w-5 h-5 mr-2" />
                Database Configuration
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Database Name
                  </label>
                  <input
                    type="text"
                    value={config.database_name}
                    onChange={(e) => handleConfigChange('database_name', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Statutes"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Source Collection
                  </label>
                  <input
                    type="text"
                    value={config.source_collection}
                    onChange={(e) => handleConfigChange('source_collection', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="raw_statutes"
                    disabled={!config.database_name}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Target Collection
                  </label>
                  <input
                    type="text"
                    value={config.target_collection}
                    onChange={(e) => handleConfigChange('target_collection', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="normalized_statutes"
                    disabled={!config.database_name}
                  />
                </div>
              </div>
              <div className="flex justify-between items-center">
                <button
                  onClick={resetConfig}
                  className="text-gray-600 hover:text-gray-800 text-sm underline"
                >
                  Reset to Defaults
                </button>
                <div className="text-sm text-gray-500">
                  Current: {config.source_collection} → {config.target_collection}
                </div>
              </div>
            </div>

            {/* Normalization Controls */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <Play className="w-5 h-5 mr-2" />
                Normalization Controls
              </h3>
              <div className="space-y-4">
                <div className="flex items-center space-x-4">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={saveMetadata}
                      onChange={(e) => setSaveMetadata(e.target.checked)}
                      className="mr-2"
                    />
                    Save metadata to file
                  </label>
                  <button
                    onClick={executeNormalization}
                    disabled={isNormalizing}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center"
                  >
                    {isNormalizing ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        {progressStep || 'Processing...'}
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 mr-2" />
                        Execute Normalization
                      </>
                    )}
                  </button>
                </div>
                
                {/* Enhanced Progress Display */}
                {isNormalizing && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-medium text-blue-900">Processing Status</h4>
                      <div className="flex items-center">
                        <Loader2 className="w-4 h-4 text-blue-600 animate-spin mr-2" />
                        <span className="text-sm text-blue-700">In Progress</span>
                      </div>
                    </div>
                    
                    {progressStep && (
                      <div className="text-sm text-blue-800 font-medium mb-1">
                        {progressStep}
                      </div>
                    )}
                    
                    {progressDetails && (
                      <div className="text-xs text-blue-600">
                        {progressDetails}
                      </div>
                    )}
                    
                    {processingStats && (
                      <div className="mt-3">
                        <div className="flex justify-between text-xs text-blue-600 mb-1">
                          <span>Progress</span>
                          <span>{processingStats.processed} / {processingStats.total}</span>
                        </div>
                        <div className="w-full bg-blue-200 rounded-full h-2">
                          <div 
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                            style={{ width: `${(processingStats.processed / processingStats.total) * 100}%` }}
                          ></div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Enhanced Error Display */}
                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <div className="flex items-center mb-2">
                      <AlertCircle className="w-4 h-4 text-red-600 mr-2" />
                      <h4 className="text-sm font-medium text-red-900">Error Details</h4>
                    </div>
                    <div className="text-sm text-red-800 mb-2">{error}</div>
                    <div className="text-xs text-red-600">
                      <strong>Suggestions:</strong>
                      <ul className="mt-1 ml-4 list-disc">
                        <li>Check database connection and permissions</li>
                        <li>Verify source collection exists and contains data</li>
                        <li>Ensure target collection name is valid</li>
                        <li>Try refreshing the page and attempting again</li>
                      </ul>
                    </div>
                  </div>
                )}
                <div className="flex space-x-2">
                  <button
                    onClick={previewNormalizedStructure}
                    className="bg-gray-600 text-white px-4 py-2 rounded-lg hover:bg-gray-700 flex items-center"
                  >
                    <Eye className="w-4 h-4 mr-2" />
                    Preview Structure
                  </button>
                  <button
                    onClick={rollbackNormalization}
                    className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 flex items-center"
                  >
                    <RotateCcw className="w-4 h-4 mr-2" />
                    Rollback
                  </button>
                </div>
              </div>
            </div>

            {/* Results Display */}
            {normalizationResult && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <CheckCircle className="w-5 h-5 mr-2 text-green-600" />
                  Normalization Results
                </h3>
                <div className="bg-green-50 p-4 rounded-lg">
                  <div className="text-green-800 font-medium">{normalizationResult.message}</div>
                  {normalizationResult.metadata && (
                    <div className="mt-3 text-sm text-green-700">
                      <div>Processed: {normalizationResult.metadata.total_documents_processed?.toLocaleString() || 0} documents</div>
                      <div>Unique Statutes: {normalizationResult.metadata.unique_statutes?.toLocaleString() || 0}</div>
                      <div>Total Sections: {normalizationResult.metadata.total_sections?.toLocaleString() || 0}</div>
                      {normalizationResult.metadata.metadata_file_path && (
                        <div>Metadata saved to: {normalizationResult.metadata.metadata_file_path}</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Preview Data */}
            {previewData && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <Eye className="w-5 h-5 mr-2" />
                  Normalized Structure Preview
                </h3>
                <div className="bg-blue-50 p-4 rounded-lg">
                  <div className="text-blue-800 font-medium">{previewData.message}</div>
                  {(previewData.total_statutes || previewData.unique_statutes_found) && (
                    <div className="mt-2 text-sm text-blue-700">
                      {previewData.total_statutes && `Total statutes: ${previewData.total_statutes.toLocaleString()}`}
                      {previewData.unique_statutes_found && `Unique statutes found: ${previewData.unique_statutes_found.toLocaleString()}`}
                      {previewData.total_raw_documents && ` (from ${previewData.total_raw_documents.toLocaleString()} raw documents)`}
                    </div>
                  )}
                  {previewData.preview_data && previewData.preview_data.length > 0 && (
                    <div className="mt-3">
                      <div className="text-sm font-medium text-blue-800 mb-2">Sample Data Structure:</div>
                      <div className="space-y-2">
                        {previewData.preview_data.map((statute: any, index: number) => (
                          <div key={index} className="bg-white p-3 rounded border">
                            <div className="font-medium text-blue-900">
                              {statute.normalized_name || statute.statute_name || statute.Statute_Name}
                            </div>
                            {statute.original_name && statute.original_name !== statute.normalized_name && (
                              <div className="text-xs text-gray-500 mb-1">
                                Original: {statute.original_name}
                              </div>
                            )}
                            <div className="text-sm text-blue-700">
                              {statute.section_count || statute.Sections?.length || 0} sections
                            </div>
                            {statute.sections_preview && statute.sections_preview.length > 0 && (
                              <div className="mt-2 text-xs text-gray-600">
                                <div className="font-medium">Sample sections:</div>
                                {statute.sections_preview.slice(0, 3).map((s: any, idx: number) => (
                                  <div key={idx} className="ml-2">
                                    • {s.section_number || s.section_type}: {s.definition || s.content_preview || ''}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* How It Works */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">How It Works</h3>
              <div className="space-y-3 text-gray-700">
                <div className="flex items-start">
                  <div className="bg-blue-100 text-blue-800 rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium mr-3 mt-0.5">1</div>
                  <div>Read all documents from the raw_statutes collection</div>
                </div>
                <div className="flex items-start">
                  <div className="bg-blue-100 text-blue-800 rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium mr-3 mt-0.5">2</div>
                  <div>Normalize statute names (remove whitespace, title case, clean special characters)</div>
                </div>
                <div className="flex items-start">
                  <div className="bg-blue-100 text-blue-800 rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium mr-3 mt-0.5">3</div>
                  <div>Group all sections by normalized statute name</div>
                </div>
                <div className="flex items-start">
                  <div className="bg-blue-100 text-blue-800 rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium mr-3 mt-0.5">4</div>
                  <div>Sort sections: preamble first, then numeric, then text</div>
                </div>
                <div className="flex items-start">
                  <div className="bg-blue-100 text-blue-800 rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium mr-3 mt-0.5">5</div>
                  <div>Build new documents with Statute_Name and Sections array</div>
                </div>
              </div>
            </div>
          </div>
        );

      case 'statute-names':
        return <StatuteNameNormalizer config={config} />;

      case 'results':
        return <ResultsPreview config={config} />;

      default:
        return null;
    }
  };

  return (
    <div className="p-4">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Phase 2: Database Normalization</h1>
        <p className="text-gray-600 mt-1 text-sm">
          Normalize and structure your legal documents with intelligent grouping and sorting
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 mb-4">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as TabType)}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="w-4 h-4 mr-2" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <AlertCircle className="w-5 h-5 text-red-400 mr-2" />
            <div className="text-red-800">{error}</div>
          </div>
        </div>
      )}

      {/* Tab Content */}
      {renderTabContent()}
    </div>
  );
};

export default Phase2;
