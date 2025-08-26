import React, { useState, useEffect, useCallback } from 'react';
import { 
  Database,
  Activity,
  Play,
  Square,
  Download,
  CheckCircle,
  Clock,
  FileText,
  Zap,
  Settings,
  BarChart3,
  Search
} from 'lucide-react';
import DateSearchTab from './DateSearchTab';

interface Phase4Status {
  current_phase: string;
  total_documents?: number;
  processed_documents?: number;
  status: string;
  available_batches?: string[];
  database_info?: {
    source_db: string;
    target_db: string;
    collections_count: number;
  };
}

interface ProcessingProgress {
  overall_progress: number;
  current_batch_progress: number;
  current_document: string;
  current_batch: string;
  documents_processed: number;
  total_documents: number;
  status: string;
  log_messages: string[];
  batch_summary?: {
    completed_batches: string[];
    current_batch: string;
    remaining_batches: string[];
  };
}

const Phase4Dashboard: React.FC = () => {
  const [status, setStatus] = useState<Phase4Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'configuration' | 'processing' | 'results' | 'merge' | 'search'>('configuration');

  // Processing Configuration State
  const [processingMode, setProcessingMode] = useState<'single' | 'all'>('all');
  const [selectedBatch, setSelectedBatch] = useState<string>('');
  const [collectionPrefix, setCollectionPrefix] = useState('batch');
  const [availableBatches, setAvailableBatches] = useState<string[]>([]);
  // Additional configuration state
  const [sourceDb, setSourceDb] = useState('Batched-Statutes');
  const [targetDb, setTargetDb] = useState('Date-Enriched-Batches');
  const [batchSize, setBatchSize] = useState<number>(100);
  const [dryRun, setDryRun] = useState<boolean>(false);
  const [generateMetadata, setGenerateMetadata] = useState<boolean>(true);
  const [testConnStatus, setTestConnStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [testConnMessage, setTestConnMessage] = useState<string>('');
  const [testGptStatus, setTestGptStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [testGptMessage, setTestGptMessage] = useState<string>('');
  
  // Processing State
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState<ProcessingProgress | null>(null);
  const [processingComplete, setProcessingComplete] = useState(false);
  
  // UI State
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  // Merge tab state
  const [metadataFiles, setMetadataFiles] = useState<any[]>([]);
  const [metadataDbEntries, setMetadataDbEntries] = useState<any[]>([]);
  const [selectedMetadata, setSelectedMetadata] = useState<any | null>(null);

  const fetchAvailableBatches = useCallback(async () => {
    try {
      const headers: any = {};
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const url = `/api/v1/phase4/available-batches?db_name=${encodeURIComponent(sourceDb)}`;
      const res = await fetch(url, { headers });
      const data = await res.json();
      if (data.success) {
        setAvailableBatches(data.batches || []);
        if (data.batches?.length > 0 && !selectedBatch) {
          setSelectedBatch(data.batches[0]);
        }
      }
    } catch (e) {
      console.error('Failed to fetch available batches:', e);
    }
  }, [sourceDb, selectedBatch]);

  useEffect(() => {
    fetchStatus();
    fetchMetadata();
    loadConfig();
  }, [fetchAvailableBatches]);

  // Refetch available batches when sourceDb changes
  useEffect(() => {
    fetchAvailableBatches();
  }, [fetchAvailableBatches]);

  // Auto-select first available batch when switching to single mode
  useEffect(() => {
    if (processingMode === 'single' && availableBatches.length > 0 && !selectedBatch) {
      setSelectedBatch(availableBatches[0]);
    }
  }, [processingMode, availableBatches, selectedBatch]);

  const loadConfig = () => {
    try {
      const raw = localStorage.getItem('phase4_config');
      if (!raw) return;
      const cfg = JSON.parse(raw);
      setSourceDb(cfg.sourceDb || 'Batched-Statutes');
      setTargetDb(cfg.targetDb || 'Date-Enriched-Batches');
      setCollectionPrefix(cfg.collectionPrefix || 'batch');
      setBatchSize(cfg.batchSize || 100);
      setDryRun(cfg.dryRun ?? false);
  setGenerateMetadata(cfg.generateMetadata ?? true);
    } catch (e) {
      console.error('Failed to load Phase4 config', e);
    }
  };

  const handleSaveConfig = () => {
    const cfg = {
      sourceDb,
      targetDb,
      collectionPrefix,
      batchSize,
      dryRun
  ,
  generateMetadata
    };
    try {
      localStorage.setItem('phase4_config', JSON.stringify(cfg));
      // small feedback - keep it minimal
      console.info('Phase4 configuration saved');
    } catch (e) {
      console.error('Failed to save config', e);
    }
  };

  const handleResetConfig = () => {
    setSourceDb('Batched-Statutes');
    setTargetDb('Date-Enriched-Batches');
    setCollectionPrefix('batch');
    setBatchSize(100);
    setDryRun(false);
  setGenerateMetadata(true);
    localStorage.removeItem('phase4_config');
  };

  const handleTestConnection = async () => {
    setTestConnStatus('testing');
    setTestConnMessage('Testing connection...');
    try {
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const headers: any = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const body = {
        connection_string: "",
        database_name: sourceDb,
        test_connection: true
      };

      const res = await fetch('/api/v1/database/connect', {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setTestConnStatus('success');
        setTestConnMessage('Connection OK — ' + (data.data?.collection_count ?? 'unknown') + ' collections');
      } else {
        setTestConnStatus('error');
        setTestConnMessage(data.detail || data.error || 'Connection failed');
      }
    } catch (e: any) {
      setTestConnStatus('error');
      setTestConnMessage(e.message || String(e));
    }
  };

  const handleTestGpt = async () => {
    setTestGptStatus('testing');
    setTestGptMessage('Testing GPT...');
    try {
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const headers: any = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch('/api/v1/phase4/test-gpt', { headers });
      const data = await res.json();
      if (res.ok && data.success) {
        setTestGptStatus('success');
        setTestGptMessage('GPT OK');
      } else {
        setTestGptStatus('error');
        setTestGptMessage(data.message || 'GPT test failed');
      }
    } catch (e: any) {
      setTestGptStatus('error');
      setTestGptMessage(e.message || String(e));
    }
  };

  const fetchStatus = async () => {
    try {
      const headers: any = {};
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      if (token) headers['Authorization'] = `Bearer ${token}`;
      
      const res = await fetch('/api/v1/phase4/status', { headers });
      const data = await res.json();
      if (data.success) {
        setStatus(data);
      }
      setLoading(false);
    } catch (e) {
      console.error(e);
      setError('Failed to fetch status');
      setLoading(false);
    }
  };

  const fetchMetadata = async () => {
    try {
      setLoading(true);
      setError(null);
      const headers: any = {};
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      if (token) headers['Authorization'] = `Bearer ${token}`;
      
      const res = await fetch('/api/v1/phase4/metadata', { headers });
      const data = await res.json();
      if (data.success) {
        setMetadataFiles(data.files || []);
        setMetadataDbEntries(data.db_entries || []);
        setSuccessMessage('Metadata refreshed successfully');
        setTimeout(() => setSuccessMessage(null), 3000);
      } else {
        setError('Failed to fetch metadata: ' + (data.message || 'Unknown error'));
      }
    } catch (e) {
      console.error('Failed to fetch metadata:', e);
      setError('Failed to refresh metadata. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  // fetchAvailableBatches is defined above with useCallback; duplicate removed.

  const handleStartProcessing = async () => {
    try {
      setIsProcessing(true);
      setProcessingComplete(false);
      setProgress(null);
      setActiveTab('processing'); // Auto-navigate to processing tab
      
      const headers: any = { 'Content-Type': 'application/json' };
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      if (token) headers['Authorization'] = `Bearer ${token}`;
      
      const requestBody = {
        processing_mode: processingMode,
        selected_batch: processingMode === 'single' ? selectedBatch : null,
  collection_prefix: collectionPrefix,
  batch_size: batchSize,
  dry_run: dryRun,
  // source_collection removed; using batch selector when single mode
  generate_metadata: generateMetadata
      };
      
      const response = await fetch('/api/v1/phase4/start-processing', {
        method: 'POST',
        headers,
        body: JSON.stringify(requestBody)
      });
      
      if (response.ok) {
        // Start listening for progress updates
        const eventSource = new EventSource('/api/v1/phase4/processing-progress');
        eventSource.onmessage = (event) => {
          const data: ProcessingProgress = JSON.parse(event.data);
          setProgress(data);
          
          if (data.status === 'completed') {
            setIsProcessing(false);
            setProcessingComplete(true);
            setActiveTab('results'); // Auto-navigate to results tab when completed
            eventSource.close();
            fetchStatus();
          } else if (data.status === 'error') {
            setIsProcessing(false);
            eventSource.close();
            setError('Processing failed: ' + data.log_messages?.slice(-1)[0]);
          }
        };
        
        eventSource.onerror = () => {
          setIsProcessing(false);
          eventSource.close();
          setError('Connection to progress stream lost');
        };
      } else {
        setIsProcessing(false);
        setError('Failed to start processing');
      }
    } catch (error) {
      console.error('Failed to start processing:', error);
      setIsProcessing(false);
      setError('Failed to start processing');
    }
  };

  const handleStopProcessing = async () => {
    try {
      const headers: any = {};
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      if (token) headers['Authorization'] = `Bearer ${token}`;
      
      await fetch('/api/v1/phase4/stop-processing', {
        method: 'POST',
        headers
      });
      
      setIsProcessing(false);
      setProgress(null);
    } catch (error) {
      console.error('Failed to stop processing:', error);
    }
  };

  const handleExportResults = async () => {
    try {
      const headers: any = {};
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      if (token) headers['Authorization'] = `Bearer ${token}`;
      
      const response = await fetch('/api/v1/phase4/export-results', {
        headers
      });
      
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `phase4_date_processed_results_${new Date().toISOString().split('T')[0]}.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error('Failed to export results:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <Database className="h-5 w-5 text-red-400" />
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Error</h3>
            <p className="mt-1 text-sm text-red-700">{error}</p>
            <button 
              onClick={() => {
                setError(null);
                fetchStatus();
              }}
              className="mt-2 text-sm text-red-600 hover:text-red-500 underline"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 flex items-center">
              <Database className="h-8 w-8 text-blue-600 mr-3" />
              Phase 4: Enhanced Date Processing
            </h2>
            <p className="text-gray-600 mt-1">
              Consolidate date fields and extract missing dates using AI assistance
            </p>
          </div>
          <div className="flex items-center space-x-4">
            {status?.database_info && (
              <div className="text-right">
                <p className="text-sm text-gray-500">Target Database</p>
                <p className="font-medium">Date-Enriched-Batches</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Success Notification */}
      {successMessage && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <CheckCircle className="h-5 w-5 text-green-400" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-green-700">{successMessage}</p>
            </div>
            <div className="ml-auto pl-3">
              <button
                onClick={() => setSuccessMessage(null)}
                className="inline-flex text-green-400 hover:text-green-500"
              >
                <span className="sr-only">Dismiss</span>
                ×
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="bg-white shadow rounded-lg">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8" aria-label="Tabs">
            <button
              onClick={() => setActiveTab('configuration')}
              className={`whitespace-nowrap py-4 px-6 border-b-2 font-medium text-sm ${
                activeTab === 'configuration'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Settings className="h-5 w-5 inline mr-2" />
              Configuration
            </button>
            <button
              onClick={async () => {
                setActiveTab('merge');
                // fetch metadata list
                try {
                  const res = await fetch('/api/v1/phase4/metadata');
                  const data = await res.json();
                  if (data.success) {
                    setMetadataFiles(data.files || []);
                    setMetadataDbEntries(data.db_entries || []);
                  }
                } catch (e) {
                  console.error('Failed to fetch metadata', e);
                }
              }}
              className={`whitespace-nowrap py-4 px-6 border-b-2 font-medium text-sm ${
                activeTab === 'merge'
                  ? 'border-green-500 text-green-600 bg-green-50'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <FileText className="h-5 w-5 inline mr-2" />
              Date Merge
            </button>
            <button
              onClick={() => setActiveTab('search')}
              className={`whitespace-nowrap py-4 px-6 border-b-2 font-medium text-sm ${
                activeTab === 'search'
                  ? 'border-purple-500 text-purple-600 bg-purple-50'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Search className="h-5 w-5 inline mr-2" />
              Date Search
            </button>
            <button
              onClick={() => setActiveTab('processing')}
              className={`whitespace-nowrap py-4 px-6 border-b-2 font-medium text-sm ${
                activeTab === 'processing'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Activity className="h-5 w-5 inline mr-2" />
              Processing
            </button>
            <button
              onClick={() => setActiveTab('results')}
              className={`whitespace-nowrap py-4 px-6 border-b-2 font-medium text-sm ${
                activeTab === 'results'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <BarChart3 className="h-5 w-5 inline mr-2" />
              Results & Export
            </button>
          </nav>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === 'configuration' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center">
                <Settings className="h-5 w-5 text-gray-600 mr-2" />
                Configuration
              </h3>

              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* Mongo URI removed - backend-managed */}

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Source Database</label>
                    <div className="flex items-center space-x-2">
                      <input type="text" value={sourceDb} onChange={(e) => setSourceDb(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                      <button onClick={handleTestConnection} className="px-3 py-2 bg-blue-600 text-white rounded-md">Test</button>
                      <button onClick={handleTestGpt} className="px-3 py-2 bg-indigo-600 text-white rounded-md">Test GPT</button>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Click Test to verify backend connection to the configured backend MongoDB (backend config is used).</p>
                    {testConnStatus !== 'idle' && (
                      <div className={`mt-2 text-sm ${testConnStatus === 'success' ? 'text-green-700' : 'text-red-700'}`}>{testConnMessage}</div>
                    )}
                    {testGptStatus !== 'idle' && (
                      <div className={`mt-2 text-sm ${testGptStatus === 'success' ? 'text-green-700' : 'text-red-700'}`}>{testGptMessage}</div>
                    )}
                  </div>
                  {/* Source Collection removed: use batch selector instead */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Target Database</label>
                    <input type="text" value={targetDb} onChange={(e) => setTargetDb(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Processing Mode Selection */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-3">Processing Mode</label>
                    <div className="space-y-2">
                      <label className="flex items-center">
                        <input type="radio" value="all" checked={processingMode === 'all'} onChange={(e) => setProcessingMode(e.target.value as 'single' | 'all')} className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300" />
                        <span className="ml-2 text-sm text-gray-700">Process All Batches</span>
                      </label>
                      <label className="flex items-center">
                        <input type="radio" value="single" checked={processingMode === 'single'} onChange={(e) => setProcessingMode(e.target.value as 'single' | 'all')} className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300" />
                        <span className="ml-2 text-sm text-gray-700">Process Single Batch</span>
                      </label>
                    </div>
                  </div>

                  {/* Batch Selection (only when single mode) */}
                  {processingMode === 'single' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Select Batch</label>
                      <select value={selectedBatch} onChange={(e) => setSelectedBatch(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-md">
                        {availableBatches.map((batch) => (
                          <option key={batch} value={batch}>{batch}</option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* Collection Prefix */}
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">Target Collection Prefix</label>
                    <input type="text" value={collectionPrefix} onChange={(e) => setCollectionPrefix(e.target.value)} placeholder="e.g., batch, filled, processed" className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                    <p className="text-xs text-gray-500 mt-1">Output collections will be named: {collectionPrefix}_1, {collectionPrefix}_2, etc.</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Batch Size</label>
                    <input type="number" value={batchSize} onChange={(e) => setBatchSize(Number(e.target.value) || 1)} min={1} className="w-full px-3 py-2 border border-gray-300 rounded-md" />
                    <p className="text-xs text-gray-500 mt-1">Number of documents to process per chunk (performance tuning).</p>
                  </div>

                  <div className="md:col-span-2 border-l pl-4">
                    <label className="flex items-center text-sm font-medium text-gray-700 mb-2">
                      <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} className="mr-2" />
                      Dry Run (do not write to target DB)
                    </label>
                  </div>
                </div>

                <div className="mt-3">
                  <label className="flex items-center text-sm font-medium text-gray-700">
                    <input type="checkbox" checked={generateMetadata} onChange={(e) => setGenerateMetadata(e.target.checked)} className="mr-2" />
                    Generate and save metadata for this run
                  </label>
                  <p className="text-xs text-gray-500 mt-1">When enabled, per-batch and overall metadata will be saved to the server metadata folder and the database.</p>
                </div>

                {/* Azure OpenAI config is backend-managed; UI fields removed */}

                {/* Available Batches Info */}
                {availableBatches.length > 0 && (
                  <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <div className="flex items-center mb-2">
                      <Database className="h-4 w-4 text-blue-600 mr-2" />
                      <span className="text-sm font-medium text-blue-800">Available Source Batches</span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {availableBatches.map((batch) => (
                        <span key={batch} className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-md font-mono">
                          {batch}
                        </span>
                      ))}
                    </div>
                    <p className="text-xs text-blue-600 mt-2">
                      Total: {availableBatches.length} batch{availableBatches.length !== 1 ? 'es' : ''} ready for processing
                    </p>
                  </div>
                )}

                {/* Configuration Summary & Next Steps */}
                <div className="mt-6 p-4 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-green-800 mb-2">Configuration Complete</h4>
                      <div className="text-sm text-green-700 space-y-1">
                        <p>• Processing mode: <span className="font-medium capitalize">{processingMode}</span></p>
                        {processingMode === 'single' && selectedBatch && (
                          <p>• Selected batch: <span className="font-medium font-mono">{selectedBatch}</span></p>
                        )}
                        <p>• Target collection prefix: <span className="font-medium font-mono">{collectionPrefix}</span></p>
                        <p>• Chunk size: <span className="font-medium">{batchSize}</span> documents per batch</p>
                        {dryRun && <p>• <span className="font-medium text-orange-600">Dry run mode enabled</span> (no data will be written)</p>}
                      </div>
                    </div>
                    <button 
                      onClick={() => setActiveTab('merge')} 
                      className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium shadow-sm"
                    >
                      <FileText className="h-4 w-4 mr-2" />
                      Start Date Merge
                    </button>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex justify-between items-center pt-4 border-t border-gray-200">
                  <div className="flex items-center space-x-3">
                    <button 
                      onClick={handleSaveConfig} 
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm font-medium"
                    >
                      Save Configuration
                    </button>
                    <button 
                      onClick={handleResetConfig} 
                      className="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors text-sm border border-gray-300"
                    >
                      Reset to Defaults
                    </button>
                  </div>
                  
                  <div className="text-xs text-gray-500">
                    Configuration saved automatically
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'processing' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center">
                <Activity className="h-5 w-5 text-gray-600 mr-2" />
                Processing Control
              </h3>
              
              <div className="flex items-center space-x-4">
                {!isProcessing ? (
                  <button
                    onClick={handleStartProcessing}
                    disabled={processingMode === 'single' && !selectedBatch}
                    className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                  >
                    <Play className="h-4 w-4 mr-2" />
                    Start Processing
                  </button>
                ) : (
                  <button
                    onClick={handleStopProcessing}
                    className="flex items-center px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
                  >
                    <Square className="h-4 w-4 mr-2" />
                    Stop Processing
                  </button>
                )}

                <div className="flex items-center space-x-2 text-sm text-gray-600">
                  {isProcessing ? (
                    <>
                      <Clock className="h-4 w-4 text-orange-500" />
                      <span>Processing...</span>
                    </>
                  ) : processingComplete ? (
                    <>
                      <CheckCircle className="h-4 w-4 text-green-500" />
                      <span>Completed</span>
                    </>
                  ) : (
                    <>
                      <Activity className="h-4 w-4 text-gray-400" />
                      <span>Ready</span>
                    </>
                  )}
                </div>
              </div>

              {/* Progress Visualization */}
              {(isProcessing || progress) && (
                <div className="space-y-4">
                  {progress && (
                    <div className="space-y-4">
                      {/* Overall Progress */}
                      <div>
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-sm font-medium text-gray-700">Overall Progress</span>
                          <span className="text-sm text-gray-600">
                            {progress.documents_processed}/{progress.total_documents} documents
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${progress.overall_progress}%` }}
                          ></div>
                        </div>
                        <div className="text-right text-xs text-gray-500 mt-1">
                          {progress.overall_progress.toFixed(1)}%
                        </div>
                      </div>

                      {/* Current Batch Progress */}
                      {progress.current_batch && (
                        <div>
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-sm font-medium text-gray-700">
                              Current Batch: {progress.current_batch}
                            </span>
                            <span className="text-sm text-gray-600">
                              {progress.current_batch_progress.toFixed(1)}%
                            </span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-green-500 h-2 rounded-full transition-all duration-300"
                              style={{ width: `${progress.current_batch_progress}%` }}
                            ></div>
                          </div>
                        </div>
                      )}

                      {/* Current Document */}
                      {progress.current_document && (
                        <div className="bg-gray-50 rounded-lg p-3">
                          <div className="flex items-center">
                            <FileText className="h-4 w-4 text-gray-500 mr-2" />
                            <span className="text-sm font-medium">Processing:</span>
                            <span className="text-sm text-gray-700 ml-2 truncate">
                              {progress.current_document}
                            </span>
                          </div>
                        </div>
                      )}

                      {/* Batch Summary */}
                      {progress.batch_summary && (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
                          <div className="bg-green-50 p-3 rounded-lg">
                            <div className="text-sm font-medium text-green-800">Completed</div>
                            <div className="text-lg font-bold text-green-900">
                              {progress.batch_summary.completed_batches.length}
                            </div>
                            <div className="text-xs text-green-600">
                              {progress.batch_summary.completed_batches.slice(-3).join(', ')}
                            </div>
                          </div>
                          <div className="bg-blue-50 p-3 rounded-lg">
                            <div className="text-sm font-medium text-blue-800">Current</div>
                            <div className="text-lg font-bold text-blue-900">
                              {progress.batch_summary.current_batch || 'None'}
                            </div>
                          </div>
                          <div className="bg-gray-50 p-3 rounded-lg">
                            <div className="text-sm font-medium text-gray-800">Remaining</div>
                            <div className="text-lg font-bold text-gray-900">
                              {progress.batch_summary.remaining_batches.length}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Live Log */}
              {progress?.log_messages && progress.log_messages.length > 0 && (
                <div>
                  <h4 className="text-md font-semibold mb-3 flex items-center">
                    <Zap className="h-4 w-4 text-gray-600 mr-2" />
                    Live Processing Log
                  </h4>
                  
                  <div className="bg-gray-900 text-green-400 font-mono text-sm p-4 rounded-lg max-h-64 overflow-y-auto">
                    {progress.log_messages.slice(-20).map((message, index) => (
                      <div key={index} className="mb-1">
                        {message}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Navigation */}
              <div className="flex justify-between">
                <button
                  onClick={() => setActiveTab('configuration')}
                  className="flex items-center px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Back to Configuration
                </button>
                {processingComplete && (
                  <button
                    onClick={() => setActiveTab('results')}
                    className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                  >
                    View Results
                    <BarChart3 className="h-4 w-4 ml-2" />
                  </button>
                )}
              </div>
            </div>
          )}
          {activeTab === 'merge' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold flex items-center">
                  <FileText className="h-5 w-5 text-gray-600 mr-2" />
                  Date Field Merge Processing
                </h3>
                <div className="flex items-center space-x-2 text-sm">
                  {isProcessing ? (
                    <div className="flex items-center text-orange-600">
                      <Clock className="h-4 w-4 mr-1 animate-pulse" />
                      Processing...
                    </div>
                  ) : processingComplete ? (
                    <div className="flex items-center text-green-600">
                      <CheckCircle className="h-4 w-4 mr-1" />
                      Completed
                    </div>
                  ) : (
                    <div className="flex items-center text-gray-500">
                      <Activity className="h-4 w-4 mr-1" />
                      Ready to Merge
                    </div>
                  )}
                </div>
              </div>

              {/* Processing Controls */}
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h4 className="text-lg font-semibold text-blue-900">Date Field Merge</h4>
                    <p className="text-blue-700 text-sm mt-1">
                      Consolidate Date and Promulgation_Date fields into a single Date field
                    </p>
                  </div>
                  <div className="flex items-center space-x-3">
                    {!isProcessing ? (
                      <button
                        onClick={async () => {
                          // Enhanced merge processing
                          const requestBody = {
                            processing_mode: processingMode,
                            selected_batch: processingMode === 'single' ? selectedBatch : null,
                            collection_prefix: collectionPrefix,
                            batch_size: batchSize,
                            dry_run: dryRun,
                            generate_metadata: generateMetadata
                          };

                          try {
                            setIsProcessing(true);
                            setProcessingComplete(false);
                            setProgress(null);

                            const res = await fetch('/api/v1/phase4/start-processing', { 
                              method: 'POST', 
                              headers: { 'Content-Type': 'application/json' }, 
                              body: JSON.stringify(requestBody) 
                            });
                            
                            if (res.ok) {
                              // Start listening for progress updates
                              const eventSource = new EventSource('/api/v1/phase4/processing-progress');
                              eventSource.onmessage = (event) => {
                                const data: ProcessingProgress = JSON.parse(event.data);
                                setProgress(data);
                                
                                if (data.status === 'completed') {
                                  setIsProcessing(false);
                                  setProcessingComplete(true);
                                  eventSource.close();
                                  // Refresh metadata and status
                                  fetchMetadata();
                                  fetchStatus();
                                }
                              };
                              
                              eventSource.onerror = () => {
                                setIsProcessing(false);
                                eventSource.close();
                              };
                            } else {
                              setIsProcessing(false);
                              alert('Failed to start merge processing');
                            }
                          } catch (e) {
                            setIsProcessing(false);
                            console.error(e);
                            alert('Failed to start merge processing');
                          }
                        }}
                        disabled={(processingMode === 'single' && !selectedBatch) || isProcessing}
                        className="flex items-center px-6 py-3 bg-gradient-to-r from-green-600 to-green-700 text-white rounded-lg hover:from-green-700 hover:to-green-800 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium shadow-lg"
                      >
                        <Play className="h-5 w-5 mr-2" />
                        Start Date Merge
                      </button>
                    ) : (
                      <button
                        onClick={handleStopProcessing}
                        className="flex items-center px-6 py-3 bg-gradient-to-r from-red-600 to-red-700 text-white rounded-lg hover:from-red-700 hover:to-red-800 font-medium shadow-lg"
                      >
                        <Square className="h-5 w-5 mr-2" />
                        Stop Processing
                      </button>
                    )}
                  </div>
                </div>

                {/* Processing Configuration Display */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div className="bg-white/70 rounded-lg p-3">
                    <div className="text-gray-600 font-medium">Mode</div>
                    <div className="text-blue-900 font-semibold capitalize">{processingMode}</div>
                  </div>
                  <div className="bg-white/70 rounded-lg p-3">
                    <div className="text-gray-600 font-medium">Batch</div>
                    <div className="text-blue-900 font-semibold">
                      {processingMode === 'single' ? selectedBatch || 'None' : 'All Batches'}
                    </div>
                  </div>
                  <div className="bg-white/70 rounded-lg p-3">
                    <div className="text-gray-600 font-medium">Chunk Size</div>
                    <div className="text-blue-900 font-semibold">{batchSize}</div>
                  </div>
                  <div className="bg-white/70 rounded-lg p-3">
                    <div className="text-gray-600 font-medium">Dry Run</div>
                    <div className="text-blue-900 font-semibold">{dryRun ? 'Yes' : 'No'}</div>
                  </div>
                </div>
              </div>

              {/* Real-time Progress Display */}
              {(isProcessing || progress) && (
                <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                  <h4 className="text-lg font-semibold mb-4 flex items-center">
                    <Activity className="h-5 w-5 text-blue-600 mr-2" />
                    Processing Progress
                  </h4>
                  
                  {progress && (
                    <div className="space-y-6">
                      {/* Overall Progress */}
                      <div>
                        <div className="flex justify-between items-center mb-3">
                          <span className="text-sm font-medium text-gray-700">Overall Progress</span>
                          <span className="text-sm font-semibold text-gray-900">
                            {progress.documents_processed?.toLocaleString()}/{progress.total_documents?.toLocaleString()} documents
                          </span>
                        </div>
                        <div className="relative w-full bg-gray-200 rounded-full h-3">
                          <div
                            className="absolute left-0 top-0 bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all duration-500 flex items-center justify-end pr-2"
                            style={{ width: `${Math.max(progress.overall_progress, 0)}%` }}
                          >
                            <span className="text-white text-xs font-bold">
                              {progress.overall_progress?.toFixed(1)}%
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Current Batch Progress */}
                      {progress.current_batch && (
                        <div>
                          <div className="flex justify-between items-center mb-3">
                            <span className="text-sm font-medium text-gray-700">
                              Current Batch: <span className="font-semibold text-gray-900">{progress.current_batch}</span>
                            </span>
                            <span className="text-sm font-semibold text-gray-900">
                              {progress.current_batch_progress?.toFixed(1)}%
                            </span>
                          </div>
                          <div className="relative w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="absolute left-0 top-0 bg-gradient-to-r from-green-500 to-green-600 h-2 rounded-full transition-all duration-500"
                              style={{ width: `${Math.max(progress.current_batch_progress || 0, 0)}%` }}
                            ></div>
                          </div>
                        </div>
                      )}

                      {/* Current Document Being Processed */}
                      {progress.current_document && (
                        <div className="bg-gradient-to-r from-gray-50 to-blue-50 rounded-lg p-4 border-l-4 border-blue-500">
                          <div className="flex items-start">
                            <FileText className="h-5 w-5 text-blue-600 mr-3 mt-0.5 flex-shrink-0" />
                            <div>
                              <div className="text-sm font-medium text-gray-700 mb-1">Currently Processing:</div>
                              <div className="text-sm text-gray-900 font-mono bg-white px-2 py-1 rounded border">
                                {progress.current_document}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Processing Statistics */}
                      {progress.batch_summary && (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div className="bg-gradient-to-br from-green-50 to-emerald-50 border border-green-200 p-4 rounded-lg">
                            <div className="flex items-center mb-2">
                              <CheckCircle className="h-5 w-5 text-green-600 mr-2" />
                              <div className="text-sm font-medium text-green-800">Completed Batches</div>
                            </div>
                            <div className="text-2xl font-bold text-green-900">
                              {progress.batch_summary.completed_batches?.length || 0}
                            </div>
                            {progress.batch_summary.completed_batches?.length > 0 && (
                              <div className="text-xs text-green-600 mt-1 truncate">
                                Latest: {progress.batch_summary.completed_batches.slice(-1)[0]}
                              </div>
                            )}
                          </div>
                          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 p-4 rounded-lg">
                            <div className="flex items-center mb-2">
                              <Activity className="h-5 w-5 text-blue-600 mr-2" />
                              <div className="text-sm font-medium text-blue-800">Current Batch</div>
                            </div>
                            <div className="text-lg font-bold text-blue-900">
                              {progress.batch_summary.current_batch || 'None'}
                            </div>
                          </div>
                          <div className="bg-gradient-to-br from-gray-50 to-slate-50 border border-gray-200 p-4 rounded-lg">
                            <div className="flex items-center mb-2">
                              <Clock className="h-5 w-5 text-gray-600 mr-2" />
                              <div className="text-sm font-medium text-gray-800">Remaining Batches</div>
                            </div>
                            <div className="text-2xl font-bold text-gray-900">
                              {progress.batch_summary.remaining_batches?.length || 0}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Live Processing Log */}
                      {progress?.log_messages && progress.log_messages.length > 0 && (
                        <div>
                          <h5 className="text-md font-semibold mb-3 flex items-center">
                            <Zap className="h-4 w-4 text-yellow-600 mr-2" />
                            Live Processing Log
                          </h5>
                          
                          <div className="bg-gray-900 text-green-400 font-mono text-sm p-4 rounded-lg max-h-48 overflow-y-auto border">
                            {progress.log_messages.slice(-15).map((message, index) => (
                              <div key={index} className="mb-1 leading-relaxed">
                                <span className="text-green-500">[{new Date().toLocaleTimeString()}]</span> {message}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Metadata and Results Section */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="text-md font-semibold text-gray-900">Metadata Files</h4>
                    <button
                      onClick={async () => {
                        try {
                          await fetchMetadata();
                        } catch (e) {
                          console.error('Refresh failed:', e);
                        }
                      }}
                      disabled={loading}
                      className="flex items-center px-3 py-1.5 text-sm bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700 disabled:bg-gray-50 disabled:text-gray-400 rounded-md transition-colors border border-blue-200"
                    >
                      {loading ? (
                        <div className="animate-spin h-3 w-3 border-2 border-blue-600 border-t-transparent rounded-full mr-1"></div>
                      ) : (
                        <Activity className="h-3 w-3 mr-1" />
                      )}
                      {loading ? 'Refreshing...' : 'Refresh'}
                    </button>
                  </div>
                  <div className="max-h-64 overflow-y-auto">
                    {metadataFiles.length === 0 ? (
                      <div className="text-sm text-gray-500 py-8 text-center">
                        No metadata files found.<br />
                        <span className="text-xs">Run processing to generate metadata</span>
                      </div>
                    ) : (
                      metadataFiles.map((f) => (
                        <div 
                          key={f.filename} 
                          className={`p-3 rounded-lg hover:bg-gray-50 cursor-pointer border mb-2 transition-colors ${
                            selectedMetadata?.filename === f.filename 
                              ? 'bg-blue-50 border-blue-200' 
                              : 'border-gray-200'
                          }`} 
                          onClick={() => setSelectedMetadata(f)}
                        >
                          <div className="flex justify-between items-start">
                            <div className="flex-1">
                              <div className="text-sm font-medium text-gray-900 mb-1">{f.filename}</div>
                              <div className="text-xs text-gray-500">
                                Modified: {new Date(f.modified * 1000).toLocaleString()}
                              </div>
                            </div>
                            <div className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                              {(f.size/1024).toFixed(1)} KB
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="text-md font-semibold text-gray-900">Database Results</h4>
                    <button
                      onClick={async () => {
                        try {
                          await fetchStatus();
                        } catch (e) {
                          console.error('Refresh failed:', e);
                        }
                      }}
                      disabled={loading}
                      className="flex items-center px-3 py-1.5 text-sm bg-green-50 text-green-600 hover:bg-green-100 hover:text-green-700 disabled:bg-gray-50 disabled:text-gray-400 rounded-md transition-colors border border-green-200"
                    >
                      {loading ? (
                        <div className="animate-spin h-3 w-3 border-2 border-green-600 border-t-transparent rounded-full mr-1"></div>
                      ) : (
                        <Database className="h-3 w-3 mr-1" />
                      )}
                      {loading ? 'Refreshing...' : 'Refresh'}
                    </button>
                  </div>
                  <div className="max-h-64 overflow-y-auto">
                    {metadataDbEntries.length === 0 ? (
                      <div className="text-sm text-gray-500 py-8 text-center">
                        No database entries found.<br />
                        <span className="text-xs">Run processing to create target collections</span>
                      </div>
                    ) : (
                      metadataDbEntries.map((d) => (
                        <div key={d._id} className="p-3 rounded-lg hover:bg-gray-50 border border-gray-200 mb-2">
                          <div className="flex justify-between items-start">
                            <div>
                              <div className="text-sm font-medium text-gray-900">{d.batch}</div>
                              <div className="text-xs text-gray-500">Target: {d.target_collection}</div>
                            </div>
                            <div className="text-right">
                              <div className="text-sm font-semibold text-green-600">
                                {d.processed?.toLocaleString()}
                              </div>
                              <div className="text-xs text-gray-500">
                                / {d.total_documents?.toLocaleString()}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-4 border-t border-gray-200">
                <button
                  onClick={async () => {
                    if (!selectedMetadata) {
                      alert('Please select a metadata file first');
                      return;
                    }
                    try {
                      const res = await fetch('/api/v1/phase4/metadata');
                      const data = await res.json();
                      const fileInfo = data.files.find((x: any) => x.filename === selectedMetadata.filename);
                      if (!fileInfo) return;
                      
                      const fileRes = await fetch('/api/v1/phase4/metadata?batch=' + encodeURIComponent(selectedMetadata.filename));
                      const fileJson = await fileRes.json();
                      
                      const blob = new Blob([JSON.stringify(fileJson, null, 2)], { type: 'application/json' });
                      const url = window.URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = selectedMetadata.filename;
                      document.body.appendChild(a);
                      a.click();
                      window.URL.revokeObjectURL(url);
                      document.body.removeChild(a);
                    } catch (e) {
                      console.error('Failed to download metadata', e);
                      alert('Failed to download metadata file');
                    }
                  }}
                  disabled={!selectedMetadata}
                  className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Download Metadata
                </button>

                {processingComplete && (
                  <button
                    onClick={() => setActiveTab('results')}
                    className="flex items-center px-6 py-2 bg-gradient-to-r from-green-600 to-green-700 text-white rounded-lg hover:from-green-700 hover:to-green-800 font-medium"
                  >
                    <BarChart3 className="h-4 w-4 mr-2" />
                    View Results & Export
                  </button>
                )}
              </div>

              {/* Selected Metadata Preview */}
              {selectedMetadata && (
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
                  <div className="flex items-center mb-3">
                    <FileText className="h-4 w-4 text-gray-600 mr-2" />
                    <span className="text-sm font-medium text-gray-900">Preview: {selectedMetadata.filename}</span>
                  </div>
                  <pre className="text-xs font-mono bg-white border rounded-lg p-3 max-h-32 overflow-y-auto">
                    {JSON.stringify(metadataDbEntries.find(d => d.batch && selectedMetadata.filename.includes(d.batch)) || {}, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
          {activeTab === 'results' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center">
                <BarChart3 className="h-5 w-5 text-gray-600 mr-2" />
                Results & Export
              </h3>

              {/* Export Controls */}
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-lg font-semibold text-green-800">Processing Complete!</h4>
                    <p className="text-green-700 mt-1">
                      Your date enrichment processing has finished successfully. You can now export the results.
                    </p>
                  </div>
                  <button
                    onClick={handleExportResults}
                    className="flex items-center px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold"
                  >
                    <Download className="h-5 w-5 mr-2" />
                    Export to Excel
                  </button>
                </div>
              </div>

              {/* Status Summary */}
              {status && (
                <div>
                  <h4 className="text-md font-semibold mb-3">Processing Summary</h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <div className="text-sm font-medium text-blue-800">Current Phase</div>
                      <div className="text-lg font-bold text-blue-900">{status.current_phase}</div>
                    </div>
                    <div className="bg-green-50 p-4 rounded-lg">
                      <div className="text-sm font-medium text-green-800">Total Documents</div>
                      <div className="text-lg font-bold text-green-900">
                        {status.total_documents?.toLocaleString() || 'N/A'}
                      </div>
                    </div>
                    <div className="bg-purple-50 p-4 rounded-lg">
                      <div className="text-sm font-medium text-purple-800">Status</div>
                      <div className="text-lg font-bold text-purple-900">{status.status}</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Final Batch Summary */}
              {progress?.batch_summary && (
                <div>
                  <h4 className="text-md font-semibold mb-3">Batch Processing Results</h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-green-50 p-4 rounded-lg">
                      <div className="text-sm font-medium text-green-800">Completed Batches</div>
                      <div className="text-lg font-bold text-green-900">
                        {progress.batch_summary.completed_batches.length}
                      </div>
                      <div className="text-xs text-green-600 mt-2">
                        {progress.batch_summary.completed_batches.join(', ')}
                      </div>
                    </div>
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <div className="text-sm font-medium text-blue-800">Documents Processed</div>
                      <div className="text-lg font-bold text-blue-900">
                        {progress.documents_processed.toLocaleString()}
                      </div>
                    </div>
                    <div className="bg-purple-50 p-4 rounded-lg">
                      <div className="text-sm font-medium text-purple-800">Success Rate</div>
                      <div className="text-lg font-bold text-purple-900">
                        {progress.overall_progress.toFixed(1)}%
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Navigation */}
              <div className="flex justify-between">
                <button
                  onClick={() => setActiveTab('processing')}
                  className="flex items-center px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Back to Processing
                </button>
                <button
                  onClick={() => {
                    setActiveTab('configuration');
                    setProcessingComplete(false);
                    setProgress(null);
                  }}
                  className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Start New Processing
                </button>
              </div>
            </div>
          )}

          {/* Date Search Tab */}
          {activeTab === 'search' && (
            <DateSearchTab />
          )}
        </div>
      </div>
    </div>
  );
};

export default Phase4Dashboard;
