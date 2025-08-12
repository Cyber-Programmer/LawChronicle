import React, { useState, useEffect } from 'react';
import { Scissors, Database, FileText, Settings, History, Eye, Play, RotateCcw, Split, Layers } from 'lucide-react';

// Configuration interface - updated to match CLI flow
interface Phase3Config {
  source_database: string;
  source_collection: string;
  target_database: string;
  target_collection_prefix: string;
  batch_size: number;
  enable_ai_cleaning: boolean;
}

// Default configuration - matches CLI scripts
const DEFAULT_CONFIG: Phase3Config = {
  source_database: "Statutes",
  source_collection: "normalized_statutes",
  target_database: "Batched-Statutes",
  target_collection_prefix: "batch_",
  batch_size: 10,
  enable_ai_cleaning: false
};

const Phase3: React.FC = () => {
  const [activeTab, setActiveTab] = useState('overview');
  const [config, setConfig] = useState<Phase3Config>(DEFAULT_CONFIG);
  const [isProcessing, setIsProcessing] = useState(false);
  const [status, setStatus] = useState<any>(null);
  const [statistics, setStatistics] = useState<any>(null);
  const [batchPreview, setBatchPreview] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [availableBatches, setAvailableBatches] = useState<any>(null);
  const [selectedBatches, setSelectedBatches] = useState<number[]>([]);
  const [cleanAllBatches, setCleanAllBatches] = useState(true);

  // Load config from localStorage on mount
  useEffect(() => {
    const savedConfig = localStorage.getItem('phase3_config');
    if (savedConfig) {
      try {
        setConfig(JSON.parse(savedConfig));
      } catch (error) {
        console.error('Error loading Phase 3 config:', error);
      }
    }
  }, []);

  // Save config to localStorage when it changes
  useEffect(() => {
    localStorage.setItem('phase3_config', JSON.stringify(config));
  }, [config]);

  // Update configuration
  const updateConfig = (updates: Partial<Phase3Config>) => {
    setConfig(prev => ({ ...prev, ...updates }));
  };

  // Reset configuration to defaults
  const resetConfig = () => {
    setConfig(DEFAULT_CONFIG);
  };

  // Fetch Phase 3 status
  const fetchStatus = async () => {
    try {
      const response = await fetch('/api/v1/phase3/status');
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      }
    } catch (error) {
      console.error('Error fetching Phase 3 status:', error);
    }
  };

  // Fetch statistics
  const fetchStatistics = async () => {
    try {
      const response = await fetch('/api/v1/phase3/statistics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      if (response.ok) {
        const data = await response.json();
        setStatistics(data);
      }
    } catch (error) {
      console.error('Error fetching Phase 3 statistics:', error);
    }
  };

  // Fetch batch preview
  const fetchBatchPreview = async () => {
    try {
      const response = await fetch('/api/v1/phase3/preview-batches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      if (response.ok) {
        const data = await response.json();
        setBatchPreview(data);
      }
    } catch (error) {
      console.error('Error fetching batch preview:', error);
    }
  };

  // Fetch history
  const fetchHistory = async () => {
    try {
      const response = await fetch('/api/v1/phase3/history');
      if (response.ok) {
        const data = await response.json();
        setHistory(data);
      }
    } catch (error) {
      console.error('Error fetching history:', error);
    }
  };

  // Fetch available batches for cleaning
  const fetchAvailableBatches = async () => {
    try {
      const response = await fetch('/api/v1/phase3/available-batches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      if (response.ok) {
        const data = await response.json();
        setAvailableBatches(data);
      }
    } catch (error) {
      console.error('Error fetching available batches:', error);
    }
  };

  // Generate metadata
  const generateMetadata = async () => {
    try {
      const response = await fetch('/api/v1/phase3/generate-metadata', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      if (response.ok) {
        const result = await response.json();
        alert(`Metadata generated successfully! File: ${result.metadata_file}`);
        fetchHistory();
      } else {
        const error = await response.json();
        alert(`Error generating metadata: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error generating metadata:', error);
      alert('Failed to generate metadata');
    }
  };

  // Start section splitting
  const startSectionSplitting = async () => {
    setIsProcessing(true);
    try {
      const response = await fetch('/api/v1/phase3/start-section-splitting', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      if (response.ok) {
        const result = await response.json();
        alert('Section splitting started successfully!');
        fetchStatus();
      } else {
        const error = await response.json();
        alert(`Error starting section splitting: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error starting section splitting:', error);
      alert('Failed to start section splitting');
    } finally {
      setIsProcessing(false);
    }
  };

  // Start field cleaning
  const startFieldCleaning = async () => {
    setIsProcessing(true);
    try {
      const response = await fetch('/api/v1/phase3/start-field-cleaning', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      if (response.ok) {
        const result = await response.json();
        alert('Field cleaning started successfully!');
        fetchStatus();
      } else {
        const error = await response.json();
        alert(`Error starting field cleaning: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error starting field cleaning:', error);
      alert('Failed to start field cleaning');
    } finally {
      setIsProcessing(false);
    }
  };

  // Start batch cleaning (new enhanced version)
  const startBatchCleaning = async () => {
    setIsProcessing(true);
    try {
      const cleaningConfig = {
        target_database: config.target_database,
        target_collection_prefix: config.target_collection_prefix,
        batch_numbers: cleanAllBatches ? null : selectedBatches,
        clean_all: cleanAllBatches
      };

      const response = await fetch('/api/v1/phase3/clean-batches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cleaningConfig)
      });
      
      if (response.ok) {
        const result = await response.json();
        alert(`Batch cleaning started successfully for ${result.batches_to_clean.length} batches!`);
        fetchStatus();
        fetchHistory(); // Refresh history to show new metadata
      } else {
        const error = await response.json();
        alert(`Error starting batch cleaning: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error starting batch cleaning:', error);
      alert('Failed to start batch cleaning');
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle batch selection
  const toggleBatchSelection = (batchNumber: number) => {
    setSelectedBatches(prev => 
      prev.includes(batchNumber) 
        ? prev.filter(n => n !== batchNumber)
        : [...prev, batchNumber]
    );
  };

  // Rollback Phase 3
  const rollbackPhase3 = async () => {
    if (!window.confirm('Are you sure you want to rollback Phase 3? This will delete all created batch collections and databases.')) {
      return;
    }

    try {
      const response = await fetch('/api/v1/phase3/rollback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      if (response.ok) {
        const result = await response.json();
        alert('Phase 3 rollback completed successfully!');
        fetchStatus();
        fetchStatistics();
      } else {
        const error = await response.json();
        alert(`Error rolling back Phase 3: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error rolling back Phase 3:', error);
      alert('Failed to rollback Phase 3');
    }
  };

  // Load data on mount
  useEffect(() => {
    fetchStatus();
    fetchStatistics();
  }, []);

  const tabs = [
    { id: 'overview', name: 'Overview', icon: Database },
    { id: 'section-splitting', name: 'Section Splitting', icon: Split },
    { id: 'field-cleaning', name: 'Field Cleaning', icon: Scissors },
    { id: 'preview', name: 'Batch Preview', icon: Eye },
    { id: 'statistics', name: 'Statistics', icon: Settings },
    { id: 'history', name: 'History', icon: History }
  ];

  return (
    <div className="space-y-0">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-2">
        <h1 className="text-xl font-bold text-gray-900 mb-1">
          Phase 3: Field Cleaning & Splitting
        </h1>
        <p className="text-gray-600 text-sm">
          Split normalized statutes into batches, then clean each batch using CLI logic
        </p>
      </div>

      {/* Current Configuration */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-2 mt-2">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold text-gray-900">Current Configuration</h2>
          <button
            onClick={resetConfig}
            className="inline-flex items-center px-3 py-1 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
          >
            <RotateCcw className="h-4 w-4 mr-1" />
            Reset to Defaults
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
          <div>
            <span className="font-medium text-gray-700">Source DB:</span>
            <input
              type="text"
              value={config.source_database}
              onChange={(e) => updateConfig({ source_database: e.target.value })}
              className="ml-2 px-2 py-1 border border-gray-300 rounded text-xs w-full"
            />
          </div>
          <div>
            <span className="font-medium text-gray-700">Source Collection:</span>
            <input
              type="text"
              value={config.source_collection}
              onChange={(e) => updateConfig({ source_collection: e.target.value })}
              className="ml-2 px-2 py-1 border border-gray-300 rounded text-xs w-full"
            />
          </div>
          <div>
            <span className="font-medium text-gray-700">Target DB:</span>
            <input
              type="text"
              value={config.target_database}
              onChange={(e) => updateConfig({ target_database: e.target.value })}
              className="ml-2 px-2 py-1 border border-gray-300 rounded text-xs w-full"
            />
          </div>
          <div>
            <span className="font-medium text-gray-700">Batch Prefix:</span>
            <input
              type="text"
              value={config.target_collection_prefix}
              onChange={(e) => updateConfig({ target_collection_prefix: e.target.value })}
              className="ml-2 px-2 py-1 border border-gray-300 rounded text-xs w-full"
            />
          </div>
          <div>
            <span className="font-medium text-gray-700">Batch Size:</span>
            <input
              type="number"
              value={config.batch_size}
              onChange={(e) => updateConfig({ batch_size: parseInt(e.target.value) || 10 })}
              className="ml-2 px-2 py-1 border border-gray-300 rounded text-xs w-16"
              min="1"
              max="50"
            />
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 mt-2">
        <nav className="flex space-x-8 px-4" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                  activeTab === tab.id
                    ? 'border-purple-500 text-purple-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.name}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mt-2">
        {activeTab === 'overview' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-blue-50 p-4 rounded-lg">
                <h3 className="text-lg font-semibold text-blue-900 mb-2 flex items-center">
                  <Split className="h-5 w-5 mr-2" />
                  Section Splitting
                </h3>
                <p className="text-blue-700 text-sm mb-3">
                  Split normalized statutes from {config.source_database}.{config.source_collection} into {config.batch_size} batches in {config.target_database}.
                </p>
                <button
                  onClick={startSectionSplitting}
                  disabled={isProcessing}
                  className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isProcessing ? 'Processing...' : 'Start Section Splitting'}
                </button>
              </div>

              <div className="bg-green-50 p-4 rounded-lg">
                <h3 className="text-lg font-semibold text-green-900 mb-2 flex items-center">
                  <Scissors className="h-5 w-5 mr-2" />
                  Field Cleaning
                </h3>
                <p className="text-green-700 text-sm mb-3">
                  Clean each batch using CLI logic: drop unnecessary fields, bring common fields up, handle single sections, remove duplicates, and sort sections.
                </p>
                <button
                  onClick={startFieldCleaning}
                  disabled={isProcessing}
                  className="w-full bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isProcessing ? 'Processing...' : 'Start Field Cleaning'}
                </button>
              </div>
            </div>

            {/* Status Overview */}
            {status && (
              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Current Status</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">
                      {status.collection_status?.source_exists ? '✅' : '❌'}
                    </div>
                    <div className="text-sm text-gray-600">Source Collection</div>
                    <div className="text-xs text-gray-500">{config.source_database}.{config.source_collection}</div>
                    {status.collection_status?.source_count > 0 && (
                      <div className="text-xs text-gray-500">{status.collection_status.source_count} documents</div>
                    )}
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">
                      {status.collection_status?.target_database_exists ? '✅' : '❌'}
                    </div>
                    <div className="text-sm text-gray-600">Target Database</div>
                    <div className="text-xs text-gray-500">{config.target_database}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-600">
                      {status.collection_status?.batch_count || 0}
                    </div>
                    <div className="text-sm text-gray-600">Batch Collections</div>
                    <div className="text-xs text-gray-500">{config.target_collection_prefix}1, {config.target_collection_prefix}2, ...</div>
                  </div>
                </div>
              </div>
            )}

            {/* Rollback Section */}
            <div className="bg-red-50 p-4 rounded-lg">
              <h3 className="text-lg font-semibold text-red-900 mb-2">Rollback</h3>
              <p className="text-red-700 text-sm mb-3">
                Rollback Phase 3 changes and restore previous state if needed.
              </p>
              <button
                onClick={rollbackPhase3}
                className="w-full bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700"
              >
                Rollback Phase 3
              </button>
            </div>
          </div>
        )}

        {activeTab === 'section-splitting' && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Section Splitting Configuration</h3>
            <div className="bg-blue-50 p-4 rounded-lg">
              <h4 className="font-medium text-blue-900 mb-2">Section Splitting Process</h4>
              <ul className="text-blue-700 text-sm space-y-1">
                <li>• Read all documents from {config.source_database}.{config.source_collection}</li>
                <li>• Split into {config.batch_size} equal batches</li>
                <li>• Create collections: {config.target_collection_prefix}1, {config.target_collection_prefix}2, ...</li>
                <li>• Distribute statutes across batches</li>
                <li>• Maintain section structure and metadata</li>
              </ul>
            </div>
            
            <div className="flex space-x-4">
              <button
                onClick={startSectionSplitting}
                disabled={isProcessing}
                className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isProcessing ? 'Processing...' : 'Start Section Splitting'}
              </button>
              <button
                onClick={generateMetadata}
                className="bg-purple-600 text-white px-6 py-2 rounded-md hover:bg-purple-700"
              >
                Generate Metadata
              </button>
              <button
                onClick={fetchStatus}
                className="bg-gray-600 text-white px-6 py-2 rounded-md hover:bg-gray-700"
              >
                Refresh Status
              </button>
            </div>
          </div>
        )}

        {activeTab === 'field-cleaning' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Field Cleaning Configuration</h3>
              <button
                onClick={fetchAvailableBatches}
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
              >
                Load Available Batches
              </button>
            </div>
            
            <div className="bg-green-50 p-4 rounded-lg">
              <h4 className="font-medium text-green-900 mb-2">Field Cleaning Process (per batch)</h4>
              <ul className="text-green-700 text-sm space-y-1">
                <li>• <strong>Drop unnecessary fields:</strong> Keep only essential fields for processing</li>
                <li>• <strong>Bring common fields up:</strong> Move fields common across all sections to statute level</li>
                <li>• <strong>Clean single-section statutes:</strong> Handle single-section statutes specially</li>
                <li>• <strong>Remove preamble duplicates:</strong> Remove duplicate preamble sections</li>
                <li>• <strong>Sort sections:</strong> Preamble first, then numeric, then text</li>
                <li>• <strong>Validate Pakistan law:</strong> Drop non-Pakistan laws using CLI logic</li>
              </ul>
            </div>

            {/* Cleaning Options */}
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium text-gray-900 mb-3">Cleaning Options</h4>
              
              <div className="space-y-3">
                <label className="flex items-center">
                  <input
                    type="radio"
                    name="cleaningMode"
                    checked={cleanAllBatches}
                    onChange={() => setCleanAllBatches(true)}
                    className="mr-2"
                  />
                  <span className="font-medium">Clean All Batches</span>
                </label>
                
                <label className="flex items-center">
                  <input
                    type="radio"
                    name="cleaningMode"
                    checked={!cleanAllBatches}
                    onChange={() => setCleanAllBatches(false)}
                    className="mr-2"
                  />
                  <span className="font-medium">Clean Selected Batches</span>
                </label>
              </div>

              {/* Batch Selection */}
              {!cleanAllBatches && availableBatches && (
                <div className="mt-4">
                  <h5 className="font-medium text-gray-700 mb-2">Select Batches to Clean:</h5>
                  <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto">
                    {availableBatches.batches.map((batch: any) => (
                      <label key={batch.batch_number} className="flex items-center space-x-2 text-sm">
                        <input
                          type="checkbox"
                          checked={selectedBatches.includes(batch.batch_number)}
                          onChange={() => toggleBatchSelection(batch.batch_number)}
                          className="rounded"
                        />
                        <span className={batch.is_cleaned ? "text-green-600" : "text-gray-700"}>
                          {batch.batch_name} ({batch.document_count} docs)
                          {batch.is_cleaned && <span className="text-xs"> ✓</span>}
                        </span>
                      </label>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    Selected: {selectedBatches.length} batches. Green items are already cleaned.
                  </p>
                </div>
              )}
            </div>
            
            <div className="flex space-x-4">
              <button
                onClick={startBatchCleaning}
                disabled={isProcessing || (!cleanAllBatches && selectedBatches.length === 0)}
                className="bg-green-600 text-white px-6 py-2 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isProcessing ? 'Processing...' : 
                  cleanAllBatches ? 'Clean All Batches' : `Clean ${selectedBatches.length} Selected Batches`}
              </button>
              <button
                onClick={generateMetadata}
                className="bg-purple-600 text-white px-6 py-2 rounded-md hover:bg-purple-700"
              >
                Generate Metadata
              </button>
              <button
                onClick={fetchStatus}
                className="bg-gray-600 text-white px-6 py-2 rounded-md hover:bg-gray-700"
              >
                Refresh Status
              </button>
            </div>
          </div>
        )}

        {activeTab === 'preview' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Batch Preview</h3>
              <button
                onClick={fetchBatchPreview}
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
              >
                Load Batch Preview
              </button>
            </div>
            
            {batchPreview ? (
              <div className="space-y-4">
                {batchPreview.batches.length > 0 ? (
                  batchPreview.batches.map((batch: any, index: number) => (
                    <div key={index} className="bg-gray-50 p-4 rounded-lg">
                      <h4 className="font-medium text-gray-900 mb-2">{batch.batch_name}</h4>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="font-medium">Documents:</span> {batch.document_count}
                        </div>
                        <div>
                          <span className="font-medium">Sample Documents:</span>
                        </div>
                      </div>
                      {batch.sample_documents && batch.sample_documents.length > 0 && (
                        <div className="mt-2">
                          <div className="text-xs text-gray-500 mb-1">Sample:</div>
                          {batch.sample_documents.map((doc: any, docIndex: number) => (
                            <div key={docIndex} className="bg-white p-2 rounded text-xs border">
                              <div><strong>Name:</strong> {doc.Statute_Name || 'N/A'}</div>
                              <div><strong>Sections:</strong> {doc.Sections?.length || 0}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <Layers className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                    <p>No batch collections found</p>
                    <p className="text-sm">Run section splitting first to create batches</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Eye className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <p>Click "Load Batch Preview" to see batch collections</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'statistics' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Processing Statistics</h3>
              <button
                onClick={fetchStatistics}
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
              >
                Load Statistics
              </button>
            </div>
            
            {statistics ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-blue-50 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {statistics.statistics?.source_collection?.count || 0}
                  </div>
                  <div className="text-sm text-blue-600">Source Documents</div>
                  <div className="text-xs text-blue-500">{statistics.statistics?.source_collection?.name}</div>
                  <div className="text-xs text-gray-500">
                    {statistics.statistics?.source_collection?.exists ? '✅ Exists' : '❌ Missing'}
                  </div>
                </div>
                
                <div className="bg-green-50 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {statistics.statistics?.target_database?.batch_collections?.length || 0}
                  </div>
                  <div className="text-sm text-green-600">Batch Collections</div>
                  <div className="text-xs text-green-500">{statistics.statistics?.target_database?.name}</div>
                  <div className="text-xs text-gray-500">
                    {statistics.statistics?.target_database?.exists ? '✅ Exists' : '❌ Missing'}
                  </div>
                </div>
                
                {statistics.statistics?.target_database?.batch_collections && (
                  <div className="md:col-span-2 bg-purple-50 p-4 rounded-lg">
                    <h4 className="font-medium text-purple-900 mb-2">Batch Collections</h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                      {statistics.statistics.target_database.batch_collections.map((batch: string, index: number) => (
                        <div key={index} className="bg-white p-2 rounded text-center">
                          <div className="font-medium">{batch}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Settings className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <p>No statistics available</p>
                <button
                  onClick={fetchStatistics}
                  className="mt-2 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
                >
                  Load Statistics
                </button>
              </div>
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Processing History</h3>
              <button
                onClick={fetchHistory}
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
              >
                Refresh History
              </button>
            </div>
            
            {history ? (
              <div className="space-y-4">
                {history.history.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Operation
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Database
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Collection
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Date
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Processed
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {history.history.map((item: any, index: number) => (
                          <tr key={index} className="hover:bg-gray-50">
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                item.operation_type === 'split' 
                                  ? 'bg-blue-100 text-blue-800' 
                                  : 'bg-green-100 text-green-800'
                              }`}>
                                {item.operation_type === 'split' ? 'Section Splitting' : 'Field Cleaning'}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {item.database}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {item.collection}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {new Date(item.created_at).toLocaleDateString()}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {item.total_processed} items
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              <button
                                onClick={() => window.open(`/api/v1/phase3/history/${item.filename}`, '_blank')}
                                className="text-indigo-600 hover:text-indigo-900"
                              >
                                View Details
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <History className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                    <p>No processing history found</p>
                    <p className="text-sm">Run section splitting or field cleaning to generate history</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <History className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <p>Click "Refresh History" to load processing history</p>
                <div className="mt-4 text-xs text-gray-500">
                  <p>• Section splitting creates batch collections</p>
                  <p>• Field cleaning processes each batch individually</p>
                  <p>• All operations are logged with timestamps</p>
                  <p>• Metadata files contain detailed statistics</p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Phase3;
