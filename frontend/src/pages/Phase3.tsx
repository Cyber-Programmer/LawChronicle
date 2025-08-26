import React, { useState, useEffect } from 'react';
import { Scissors, Database, FileText, Settings, History, Eye, Play, RotateCcw, Split, Layers, Loader2, AlertCircle } from 'lucide-react';

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
  const [progressStep, setProgressStep] = useState<string>('');
  const [progressDetails, setProgressDetails] = useState<string>('');
  const [processingStats, setProcessingStats] = useState<{processed: number, total: number, operation: string} | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [prefixError, setPrefixError] = useState<string | null>(null);
  const [history, setHistory] = useState<any>(null);
  const [availableBatches, setAvailableBatches] = useState<any>(null);
  const [diagnostics, setDiagnostics] = useState<any>(null);
  const [selectedBatches, setSelectedBatches] = useState<number[]>([]);
  const [cleanAllBatches, setCleanAllBatches] = useState(true);
  const [dryRun, setDryRun] = useState(true);
  const [validationResults, setValidationResults] = useState<any>(null);
  const [saveMetadata, setSaveMetadata] = useState<boolean>(true);
  const [expandedStatutes, setExpandedStatutes] = useState<{[key: string]: boolean}>({});
  const [expandedSections, setExpandedSections] = useState<{[key: string]: boolean}>({});

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
    const newConfig = { ...config, ...updates };
    setConfig(newConfig);
    // Validate prefix
    if ('target_collection_prefix' in updates) {
      const v = (updates as any).target_collection_prefix as string;
      validatePrefix(v);
    }
  };

  const validatePrefix = (prefix: string) => {
    if (!prefix || !prefix.trim()) {
      setPrefixError('Prefix cannot be empty');
      return false;
    }
    const ok = /^[A-Za-z0-9_-]{1,50}$/.test(prefix.trim());
    if (!ok) {
      setPrefixError('Use only letters, numbers, underscore or hyphen (1-50 chars)');
      return false;
    }
    if (prefix.trim().startsWith('$') || prefix.trim().toLowerCase().startsWith('system')) {
      setPrefixError('Prefix cannot start with "$" or "system"');
      return false;
    }
    setPrefixError(null);
    return true;
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

  // Refresh status and related data; when on Pakistan tab also refresh available batches
  const refreshStatus = async () => {
    await fetchStatus();
    // If user is on Pakistan validation tab, refresh batch listings so document counts update
    if (activeTab === 'pakistan-law-validation') {
      await fetchAvailableBatches();
    }
    // If on statistics tab refresh stats as well
    if (activeTab === 'statistics') {
      await fetchStatistics();
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

  // Start section splitting using modern service endpoint
  const startSectionSplitting = async () => {
    setIsProcessing(true);
    setOperationError(null);
    setProgressStep('Initializing section splitting process...');
    setProgressDetails('Preparing to analyze and split statute sections');
    setProcessingStats(null);
    
    try {
      // Step 1: Prepare request
      setProgressStep('Preparing section splitting request');
      setProgressDetails(`Source: ${config.source_database}.${config.source_collection} → Target: ${config.target_database}.${config.target_collection_prefix}*`);
      
      // Step 2: Send to the correct endpoint
      setProgressStep('Connecting to section splitting service');
      setProgressDetails('Analyzing statute structure and splitting into batches...');

      const response = await fetch('/api/v1/phase3/start-section-splitting', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      // Step 3: Process results
      setProgressStep('Processing section splitting results');
      setProgressDetails('Analyzing split sections and organizing data...');
      
      if (response.ok) {
        const result = await response.json();
        setProgressStep('Section splitting completed successfully!');
        setProgressDetails(`Successfully created ${result.batches_created || 0} batch collections`);
        
        // Show success notification with details
        const batchCount = result.batches_created || 0;
        setProcessingStats({
          processed: batchCount,
          total: batchCount,
          operation: 'Section Splitting'
        });
        
        fetchStatus();
        
        // Clear progress after delay
        setTimeout(() => {
          setProgressStep('');
          setProgressDetails('');
          setProcessingStats(null);
        }, 3000);
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Section splitting failed');
      }
    } catch (error) {
      setProgressStep('Error during section splitting');
      const errorMessage = error instanceof Error ? error.message : 'Failed to start section splitting';
      setProgressDetails(errorMessage);
      setOperationError(errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };

  // Start field cleaning using modern service endpoint
  const startFieldCleaning = async () => {
    setIsProcessing(true);
    setOperationError(null);
    setProgressStep('Initializing field cleaning process...');
    setProgressDetails('Preparing to clean and validate field data');
    setProcessingStats(null);
    
    try {
      // Step 1: Prepare cleaning request (send the Phase3 config)
      setProgressStep('Preparing field cleaning request');
      setProgressDetails(`Scheduling cleaning for collections with prefix: ${config.target_collection_prefix}`);

      // Step 2: Schedule cleaning on the backend (background task)
      setProgressStep('Scheduling field cleaning on server');
      setProgressDetails('Requesting server to start field cleaning in background...');

      const response = await fetch('/api/v1/phase3/start-field-cleaning', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      // Step 3: Process cleaning results
      setProgressStep('Processing field cleaning results');
      setProgressDetails('Validating cleaned data and updating collections...');
      
      if (response.ok) {
        const result = await response.json();
        const batches = result.batches_scheduled || [];

        setProgressStep('Field cleaning scheduled');
        setProgressDetails(`Cleaning scheduled for ${batches.length} batches. Server is processing in background.`);

        setProcessingStats({
          processed: batches.length,
          total: batches.length || 1,
          operation: 'Field Cleaning'
        });

  fetchStatus();
  // Refresh available batches so cleaned flags update immediately
  fetchAvailableBatches();
  fetchHistory(); // refresh history to show new metadata

        // Clear progress after short delay but keep status visible
        setTimeout(() => {
          setProgressStep('');
          setProgressDetails('');
        }, 3000);
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Field cleaning scheduling failed');
      }
    } catch (error) {
      setProgressStep('Error during field cleaning');
      const errorMessage = error instanceof Error ? error.message : 'Failed to start field cleaning';
      setProgressDetails(errorMessage);
      setOperationError(errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };

  // Start batch cleaning (using service architecture)
  const startBatchCleaning = async () => {
    setIsProcessing(true);
    try {
      // Build payload matching the backend BatchCleaningConfig model
      const payload = {
        target_database: config.target_database,
        target_collection_prefix: config.target_collection_prefix,
        batch_numbers: cleanAllBatches ? null : selectedBatches,
        clean_all: cleanAllBatches
      };

      // Call the dedicated endpoint that schedules cleaning for selected batches
      const response = await fetch('/api/v1/phase3/clean-batches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        const result = await response.json();
        alert('Batch cleaning started successfully!');
  // Refresh status and batches so UI reflects scheduled cleaning
  refreshStatus();
  fetchHistory();
      } else {
        const error = await response.json();
        alert(`Error starting batch cleaning: ${error.detail || error.message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error starting batch cleaning:', error);
      alert('Failed to start batch cleaning');
    } finally {
      setIsProcessing(false);
    }
  };
  // Start Pakistan Law Validation
  const startPakistanLawValidation = async () => {
    setIsProcessing(true);
    setValidationResults(null);
    try {
      const payload = {
        target_database: config.target_database,
        target_collection_prefix: config.target_collection_prefix,
        batch_numbers: cleanAllBatches ? null : selectedBatches,
        clean_all: cleanAllBatches
      };
  const url = `/api/v1/phase3/validate-pakistan-batches?dry_run=${dryRun}&save_metadata=${saveMetadata}`;
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (response.ok) {
        const result = await response.json();
        setValidationResults(result);
        fetchStatus();
        fetchHistory();
      } else {
        const err = await response.json();
        alert(`Error during validation: ${err.message || err.detail}`);
      }
    } catch (error) {
      console.error('Error validating Pakistan law batches:', error);
      alert('Pakistan law validation failed');
    } finally {
      setIsProcessing(false);
    }
  };

  // Preview validation metadata
  const previewValidationMetadata = async () => {
    setIsProcessing(true);
    try {
      const payload = {
        target_database: config.target_database,
        target_collection_prefix: config.target_collection_prefix,
        batch_numbers: cleanAllBatches ? null : selectedBatches,
        clean_all: cleanAllBatches
      };
      const response = await fetch('/api/v1/phase3/preview-validation-metadata', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (response.ok) {
        const result = await response.json();
        alert(`Metadata Preview:\n\nEstimated Documents: ${result.estimated_documents}\nBatches: ${result.batches_to_process.length}\n\nMetadata structure generated successfully!`);
      } else {
        const err = await response.json();
        alert(`Error previewing metadata: ${err.message || err.detail}`);
      }
    } catch (error) {
      console.error('Error previewing validation metadata:', error);
      alert('Metadata preview failed');
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

  // Toggle statute expansion
  const toggleStatuteExpansion = (statuteKey: string) => {
    setExpandedStatutes(prev => ({
      ...prev,
      [statuteKey]: !prev[statuteKey]
    }));
  };

  // Toggle section expansion
  const toggleSectionExpansion = (sectionKey: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [sectionKey]: !prev[sectionKey]
    }));
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
  // Auto-load batches when Pakistan Law Validation tab is active
  useEffect(() => {
    if (activeTab === 'pakistan-law-validation') {
      fetchAvailableBatches();
    }
  }, [activeTab]);

  const tabs = [
    { id: 'overview', name: 'Overview', icon: Database },
    { id: 'section-splitting', name: 'Section Splitting', icon: Split },
    { id: 'field-cleaning', name: 'Field Cleaning', icon: Scissors },
    { id: 'pakistan-law-validation', name: 'Pakistan Law Validation', icon: FileText },
    { id: 'preview', name: 'Batch Preview', icon: Eye },
    { id: 'statistics', name: 'Statistics', icon: Settings },
    { id: 'history', name: 'History', icon: History }
  ];
  // Start Pakistan Law Validation (mirrors batch cleaning, but uses different processing_type)

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
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
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
                {prefixError && (
                  <div className="text-xs text-red-600 mt-1">{prefixError}</div>
                )}
              </div>
          <div>
            <span className="font-medium text-gray-700">Number of Batches:</span>
            <input
              type="number"
              value={config.batch_size}
              onChange={(e) => updateConfig({ batch_size: parseInt(e.target.value) || 10 })}
              className="ml-2 px-2 py-1 border border-gray-300 rounded text-xs w-16"
              min="1"
              max="50"
            />
          </div>
          {/* AI-enhanced cleaning option hidden while feature is under review for interviews */}
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
                  Split normalized statutes from {config.source_database}.{config.source_collection} into {config.batch_size} equal batches in {config.target_database}.
                </p>
                <button
                  onClick={startSectionSplitting}
                  disabled={isProcessing}
                  className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isProcessing ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 inline animate-spin" />
                      {progressStep || 'Processing...'}
                    </>
                  ) : (
                    'Start Section Splitting'
                  )}
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
                  disabled={isProcessing || !!prefixError}
                  className="w-full bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isProcessing ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 inline animate-spin" />
                      {progressStep || 'Processing...'}
                    </>
                  ) : (
                    'Start Field Cleaning'
                  )}
                </button>
              </div>
            </div>

            {/* Enhanced Processing Progress Display */}
            {isProcessing && (
              <div className="bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-lg p-6 mb-6">
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
                        style={{ width: `${(processingStats.processed / processingStats.total) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Enhanced Error Display */}
            {operationError && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-6 mb-6">
                <div className="flex items-start">
                  <AlertCircle className="w-5 h-5 text-red-600 mr-3 mt-0.5" />
                  <div className="flex-1">
                    <h3 className="text-base font-medium text-red-900 mb-2">Operation Failed</h3>
                    <div className="text-sm text-red-800 mb-3">{operationError}</div>
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
                    <button
                      onClick={() => setOperationError(null)}
                      className="mt-3 text-sm text-red-600 hover:text-red-800 underline"
                    >
                      Dismiss error
                    </button>
                  </div>
                </div>
              </div>
            )}

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
                <li>• Split into exactly {config.batch_size} batches with documents distributed evenly</li>
                <li>• Create collections: {config.target_collection_prefix}1, {config.target_collection_prefix}2, ...</li>
                <li>• Distribute statutes across batches as evenly as possible</li>
                <li>• Maintain section structure and metadata</li>
              </ul>
            </div>
            
            <div className="flex space-x-4">
              <button
                onClick={startSectionSplitting}
                disabled={isProcessing || !!prefixError}
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
                disabled={isProcessing || !!prefixError || (!cleanAllBatches && selectedBatches.length === 0)}
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
                onClick={refreshStatus}
                className="bg-gray-600 text-white px-6 py-2 rounded-md hover:bg-gray-700"
              >
                Refresh Status
              </button>
              <button
                onClick={async () => {
                  try {
                    setIsProcessing(true);
                    const response = await fetch('/api/v1/phase3/batch-diagnostics', {
                      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config)
                    });
                    if (response.ok) {
                      const data = await response.json();
                      setDiagnostics(data.batches || []);
                    } else {
                      const err = await response.json();
                      alert('Diagnostics failed: ' + (err.detail || err.message));
                    }
                  } catch (e) {
                    console.error('Diagnostics error', e);
                    alert('Diagnostics failed');
                  } finally {
                    setIsProcessing(false);
                  }
                }}
                className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700"
              >
                Run Diagnostics
              </button>
            </div>
            {diagnostics && diagnostics.length > 0 && (
              <div className="mt-4 bg-white p-3 rounded border text-sm">
                <h4 className="font-medium mb-2">Batch Diagnostics</h4>
                {diagnostics.map((d: any) => (
                  <div key={d.batch_name} className="mb-2">
                    <strong>{d.batch_name}</strong>: total={d.total_documents}, legacy_cleaned={d.legacy_cleaned_count}, modern_cleaned={d.modern_cleaned_count}, any_cleaned={d.any_cleaned_count}
                    <div className="text-xs text-gray-600 mt-1">legacy sample ids: {d.legacy_samples.join(', ') || 'none'}</div>
                    <div className="text-xs text-gray-600">modern sample ids: {d.modern_samples.join(', ') || 'none'}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {/* Pakistan Law Validation Tab */}
        {activeTab === 'pakistan-law-validation' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center">
              <label className="flex items-center mr-4">
                <input type="checkbox" checked={dryRun} onChange={e => setDryRun(e.target.checked)} className="mr-2" />
                <span className="font-medium">Dry Run (Preview Only)</span>
              </label>
              <span className="text-xs text-gray-500">Preview which statutes will be dropped before actual deletion.</span>
            </div>
              <div className="flex items-center">
              <label className="flex items-center mr-4">
                <input type="checkbox" checked={saveMetadata} onChange={e => setSaveMetadata(e.target.checked)} className="mr-2" />
                <span className="font-medium text-sm">Generate Metadata</span>
              </label>
              <span className="text-xs text-gray-500">Save validation statistics and analysis.</span>
            </div>
          </div>
          {validationResults && (
            <div className="bg-gray-50 p-4 rounded-lg mt-4">
              <div className="flex justify-between items-center mb-2">
                <h4 className="font-medium text-gray-900">Validation Results</h4>
                {validationResults.metadata_file && (
                  <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
                    📁 Metadata: {validationResults.metadata_file}
                  </span>
                )}
              </div>
              <div className="mb-2 text-sm">
                <strong>Scanned:</strong> {validationResults.total_scanned} &nbsp;
                <strong>Dropped:</strong> {validationResults.total_dropped} &nbsp;
                <strong>Kept:</strong> {validationResults.total_kept} &nbsp;
                <strong>Batches:</strong> {validationResults.processed_batches}
              </div>
              {validationResults.metadata && (
                <div className="mb-2 text-xs bg-white p-2 rounded border">
                  <strong>Drop Analysis:</strong>
                  <div className="grid grid-cols-2 gap-2 mt-1">
                    <div>Drop Rate: {validationResults.metadata.validation_results?.drop_rate?.toFixed(1)}%</div>
                    <div>Keep Rate: {validationResults.metadata.validation_results?.keep_rate?.toFixed(1)}%</div>
                  </div>
                  {validationResults.metadata.drop_reason_analysis?.top_drop_reasons && (
                    <div className="mt-1">
                      <strong>Top Reasons:</strong> {validationResults.metadata.drop_reason_analysis.top_drop_reasons.map(([reason, count]: [string, number]) => `${reason} (${count})`).join(', ')}
                    </div>
                  )}
                </div>
              )}
              {validationResults.dropped_docs.length > 0 && (
                <div className="mb-2">
                  <strong>Dropped Statutes:</strong>
                  <ul className="list-disc ml-6 text-xs">
                    {validationResults.dropped_docs.map((doc: any, idx: number) => (
                      <li key={doc.name + idx}>
                        {doc.name}
                        <span className="text-red-600"> ({doc.reason})</span>
                        <span className="text-gray-500"> [{doc.batch}]</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {validationResults.kept_docs.length > 0 && (
                <div className="mb-2">
                  <strong>Kept Statutes:</strong>
                  <ul className="list-disc ml-6 text-xs">
                    {validationResults.kept_docs.map((doc: any, idx: number) => (
                      <li key={doc.name + idx}>
                        {doc.name}
                        <span className="text-green-600"> [Kept]</span>
                        <span className="text-gray-500"> [{doc.batch}]</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="text-xs text-gray-500">{validationResults.dry_run ? "No changes made (preview only)" : "Non-Pakistan statutes have been dropped."}</div>
            </div>
          )}
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Pakistan Law Validation Configuration</h3>
              <button
                onClick={fetchAvailableBatches}
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
              >Load Available Batches</button>
            </div>
            <div className="bg-yellow-50 p-4 rounded-lg">
              <ul className="text-yellow-700 text-sm space-y-1">
                <li>• Drop non-Pakistan laws using CLI logic</li>
                <li>• Validate all or selected batches</li>
              </ul>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="space-y-3">
                <label className="flex items-center"><input type="radio" checked={cleanAllBatches} onChange={() => setCleanAllBatches(true)} className="mr-2"/>Validate All</label>
                <label className="flex items-center"><input type="radio" checked={!cleanAllBatches} onChange={() => setCleanAllBatches(false)} className="mr-2"/>Validate Selected</label>
              </div>
              {/* Show guidance when batches not loaded */}
              {availableBatches === null && (
                <div className="text-center py-4 text-gray-500">
                  Click "Load Available Batches" to load batches for validation
                </div>
              )}
              {/* Batch Selection */}
              {/* Batch Selection */}
              {!cleanAllBatches && availableBatches && availableBatches.batches.length > 0 && (
                <div className="mt-4 grid grid-cols-3 gap-2 max-h-48 overflow-y-auto">
                  {availableBatches.batches.map((b: any) => (
                    <label key={b.batch_number} className="flex items-center space-x-2 text-sm">
                      <input type="checkbox" checked={selectedBatches.includes(b.batch_number)} onChange={() => toggleBatchSelection(b.batch_number)} className="rounded"/>
                      <span className={b.is_cleaned ? 'text-green-600' : 'text-gray-700'}>{b.batch_name} ({b.document_count})</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
            {/* No batches fallback */}
            {availableBatches && availableBatches.batches.length === 0 && (
              <div className="text-center py-4 text-gray-500">
                No batch collections found. Run section splitting first to create batches.
              </div>
            )}
            <div className="flex space-x-4">
              <button onClick={startPakistanLawValidation} disabled={isProcessing || !!prefixError || (!cleanAllBatches && selectedBatches.length===0)} className="bg-yellow-600 text-white px-6 py-2 rounded-md hover:bg-yellow-700 disabled:opacity-50">{isProcessing?'Processing...':(cleanAllBatches?'Validate All':'Validate Selected')}</button>
              <button onClick={previewValidationMetadata} disabled={isProcessing || !!prefixError || (!cleanAllBatches && selectedBatches.length===0)} className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50">Preview Metadata</button>
              <button onClick={refreshStatus} className="bg-gray-600 text-white px-6 py-2 rounded-md hover:bg-gray-700">Refresh Status</button>
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
                      <div className="grid grid-cols-2 gap-4 text-sm mb-3">
                        <div>
                          <span className="font-medium">Documents:</span> {batch.document_count}
                        </div>
                        <div>
                          <span className="font-medium">Sample Documents:</span> {batch.sample_documents?.length || 0}
                        </div>
                      </div>
                      
                      {batch.sample_documents && batch.sample_documents.length > 0 && (
                        <div className="space-y-2">
                          <div className="text-xs text-gray-500 mb-2">Sample Documents (click to expand):</div>
                          {batch.sample_documents.map((doc: any, docIndex: number) => {
                            const statuteKey = `${batch.batch_name}-${docIndex}`;
                            const isStatuteExpanded = expandedStatutes[statuteKey];
                            
                            return (
                              <div key={docIndex} className="bg-white border rounded-lg">
                                {/* Statute Header */}
                                <div 
                                  className="p-3 cursor-pointer hover:bg-gray-50 flex items-center justify-between"
                                  onClick={() => toggleStatuteExpansion(statuteKey)}
                                >
                                  <div className="flex-1">
                                    <div className="font-medium text-sm text-gray-900">
                                      {doc.Statute_Name || 'N/A'}
                                    </div>
                                    <div className="text-xs text-gray-500">
                                      {doc.Sections?.length || 0} sections • Province: {doc.Province || 'N/A'}
                                    </div>
                                  </div>
                                  <div className="text-gray-400">
                                    {isStatuteExpanded ? '▼' : '▶'}
                                  </div>
                                </div>
                                
                                {/* Expanded Sections */}
                                {isStatuteExpanded && doc.section_details && (
                                  <div className="border-t border-gray-100">
                                    {doc.section_details.map((section: any, sectionIndex: number) => {
                                      const sectionKey = `${statuteKey}-section-${sectionIndex}`;
                                      const isSectionExpanded = expandedSections[sectionKey];
                                      
                                      return (
                                        <div key={sectionIndex} className="border-b border-gray-50 last:border-b-0">
                                          {/* Section Header */}
                                          <div 
                                            className="p-3 pl-6 cursor-pointer hover:bg-gray-25 flex items-center justify-between"
                                            onClick={() => toggleSectionExpansion(sectionKey)}
                                          >
                                            <div className="flex-1">
                                              <div className="font-medium text-sm text-blue-900">
                                                {section.section_title}
                                              </div>
                                              <div className="text-xs text-gray-500 mt-1">
                                                {section.content_preview}
                                              </div>
                                            </div>
                                            <div className="text-gray-400 text-sm">
                                              {isSectionExpanded ? '▼' : '▶'}
                                            </div>
                                          </div>
                                          
                                          {/* Full Section Content */}
                                          {isSectionExpanded && (
                                            <div className="p-3 pl-8 bg-gray-50 border-t border-gray-100">
                                              <div className="text-sm text-gray-800 whitespace-pre-wrap">
                                                {section.content || 'No content available'}
                                              </div>
                                            </div>
                                          )}
                                        </div>
                                      );
                                    })}
                                  </div>
                                )}
                                
                                {/* Fallback for documents without section_details */}
                                {isStatuteExpanded && !doc.section_details && doc.Sections && (
                                  <div className="border-t border-gray-100 p-3">
                                    <div className="text-xs text-gray-500 mb-2">Basic Section Info:</div>
                                    {doc.Sections.map((section: any, sectionIndex: number) => (
                                      <div key={sectionIndex} className="text-xs text-gray-700 mb-1">
                                        • {section.Section || `Section ${sectionIndex + 1}`}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })}
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
