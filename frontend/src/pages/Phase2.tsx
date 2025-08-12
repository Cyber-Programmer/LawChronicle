import React, { useState } from 'react';
import { Database, Play, Eye, RotateCcw, FileText, BarChart3, CheckCircle, AlertCircle, Loader2, Settings, History, List, SortAsc } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import StatuteNameNormalizer from '../components/phase2/StatuteNameNormalizer';
import StructureCleaner from '../components/phase2/StructureCleaner';
import SortingInterface from '../components/phase2/SortingInterface';
import ProgressTracker from '../components/phase2/ProgressTracker';
import ResultsPreview from '../components/phase2/ResultsPreview';
import NormalizationHistory from '../components/phase2/NormalizationHistory';

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
  preview_data?: any[];
  data_structure?: any;
}

interface NormalizationConfig {
  source_collection: string;
  target_collection: string;
  database_name?: string;
  cleaned_collection: string;
  sorted_collection: string;
}

type TabType = 'overview' | 'statute-names' | 'structure-cleaner' | 'sorting' | 'progress' | 'results' | 'history';

const Phase2: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [isNormalizing, setIsNormalizing] = useState(false);
  const [saveMetadata, setSaveMetadata] = useState(false);
  const [normalizationResult, setNormalizationResult] = useState<NormalizationResult | null>(null);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [statusInfo, setStatusInfo] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Configuration state
  const [config, setConfig] = useState<NormalizationConfig>({
    source_collection: "raw_statutes",
    target_collection: "normalized_statutes",
    database_name: "",
    cleaned_collection: "cleaned_statutes",
    sorted_collection: "sorted_statutes"
  });

  const executeNormalization = async () => {
    setIsNormalizing(true);
    setError(null);
    setNormalizationResult(null);

    try {
      const response = await fetch(`/api/v1/phase2/execute-normalization?save_metadata=${saveMetadata}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(config)
      });

      const result = await response.json();
      
      if (response.ok) {
        setNormalizationResult(result);
        // Refresh status after successful normalization
        await getNormalizationStatus();
      } else {
        setError(result.detail?.message || result.message || 'Normalization failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      setIsNormalizing(false);
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
        setError('Failed to preview normalized structure');
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
      database_name: "",
      cleaned_collection: "cleaned_statutes",
      sorted_collection: "sorted_statutes"
    });
  };

  React.useEffect(() => {
    getNormalizationStatus();
  }, []);

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Database },
    { id: 'statute-names', label: 'Statute Names', icon: FileText },
    { id: 'structure-cleaner', label: 'Structure Cleaner', icon: Settings },
    { id: 'sorting', label: 'Sorting Interface', icon: SortAsc },
    { id: 'progress', label: 'Progress Tracker', icon: BarChart3 },
    { id: 'results', label: 'Results Preview', icon: Eye },
    { id: 'history', label: 'Normalization History', icon: History }
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
                    Source Collection
                  </label>
                  <input
                    type="text"
                    value={config.source_collection}
                    onChange={(e) => handleConfigChange('source_collection', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="raw_statutes"
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
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Database Name (optional)
                  </label>
                  <input
                    type="text"
                    value={config.database_name}
                    onChange={(e) => handleConfigChange('database_name', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Leave empty for default"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Cleaned Collection
                  </label>
                  <input
                    type="text"
                    value={config.cleaned_collection}
                    onChange={(e) => handleConfigChange('cleaned_collection', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="cleaned_statutes"
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
                        Processing...
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 mr-2" />
                        Execute Normalization
                      </>
                    )}
                  </button>
                </div>
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
                  {previewData.total_statutes && (
                    <div className="mt-2 text-sm text-blue-700">
                      Total statutes: {previewData.total_statutes.toLocaleString()}
                    </div>
                  )}
                  {previewData.preview_data && previewData.preview_data.length > 0 && (
                    <div className="mt-3">
                      <div className="text-sm font-medium text-blue-800 mb-2">Sample Data Structure:</div>
                      <div className="space-y-2">
                        {previewData.preview_data.map((statute: any, index: number) => (
                          <div key={index} className="bg-white p-3 rounded border">
                            <div className="font-medium text-blue-900">{statute.Statute_Name}</div>
                            <div className="text-sm text-blue-700">
                              {statute.Sections?.length || 0} sections
                            </div>
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

      case 'structure-cleaner':
        return <StructureCleaner config={config} />;

      case 'sorting':
        return <SortingInterface config={config} />;

      case 'progress':
        return <ProgressTracker config={config} />;

      case 'results':
        return <ResultsPreview config={config} />;

      case 'history':
        return <NormalizationHistory config={config} />;

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
