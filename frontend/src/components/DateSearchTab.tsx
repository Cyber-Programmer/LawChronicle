import React, { useState, useEffect, useRef } from 'react';
import { Search, Download, Upload, FileSpreadsheet, Brain, CheckCircle, AlertCircle, RefreshCw, StopCircle, Eye } from 'lucide-react';
import apiClient from '../services/authService';

interface ScanResults {
  scan_id: string;
  collections_scanned: string[];
  summary: {
    total_documents: number;
    documents_with_dates: number;
    documents_missing_dates: number;
    missing_percentage: number;
  };
  collection_breakdown: Record<string, {
    total_documents: number;
    missing_dates: number;
    missing_percentage: number;
  }>;
  sample_missing: Array<{
    _id: string;
    Statute_Name: string;
    Province: string;
    collection: string;
  }>;
}

interface SearchSession {
  session_id: string;
  created_at: string;
  session_label?: string;
  created_at_local?: string;
  status: string;
  total_documents: number;
  metadata: {
    source_collections: string[];
    ai_processed: number;
    high_confidence: number;
  };
}

interface ProgressData {
  progress: number;
  current_collection?: string;
  collections_processed?: number;
  total_collections?: number;
  current_statute?: string;
  processed_count?: number;
}

const DateSearchTab: React.FC = () => {
  const [availableCollections, setAvailableCollections] = useState<string[]>([]);
  const [selectedCollections, setSelectedCollections] = useState<string[]>([]);
  const [scanResults, setScanResults] = useState<ScanResults | null>(null);
  const [searchSessions, setSearchSessions] = useState<SearchSession[]>([]);
  const [currentOperation, setCurrentOperation] = useState<{
    type: 'scan' | 'search';
    id: string;
    status: 'running' | 'completed' | 'error' | 'stopped';
  } | null>(null);
  const [progress, setProgress] = useState<ProgressData>({ progress: 0 });
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [lastUploadedFile, setLastUploadedFile] = useState<File | null>(null);
  const [lastUploadedSessionId, setLastUploadedSessionId] = useState<string | null>(null);
  const [applyResult, setApplyResult] = useState<any | null>(null);
  
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    fetchAvailableCollections();
    fetchSearchSessions();
  }, []);

  useEffect(() => {
    // Auto-dismiss messages
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  useEffect(() => {
    // Cleanup EventSource on unmount
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const fetchAvailableCollections = async () => {
    try {
      const response = await apiClient.get('/phase4/search/collections');
      setAvailableCollections(response.data.collections);
      setSelectedCollections(response.data.collections); // Select all by default
    } catch (err) {
      setError('Failed to fetch collections');
      console.error('Fetch collections error:', err);
    }
  };

  const fetchSearchSessions = async () => {
    try {
      const response = await apiClient.get('/phase4/search/search-sessions');
      setSearchSessions(response.data.sessions);
    } catch (err) {
      console.error('Fetch search sessions error:', err);
    }
  };

  const viewSearchResults = async (sessionId: string) => {
    try {
      setLoading(prev => ({ ...prev, viewResults: true }));
      const response = await apiClient.get(`/phase4/search/search-results/${sessionId}`, {
        responseType: 'blob'
      });
      
      // Create download link for Excel file
      const blob = new Blob([response.data], { 
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Extract filename from Content-Disposition header or use default
      const contentDisposition = response.headers['content-disposition'];
      let filename = `search-results-${sessionId}.xlsx`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename=([^;]+)/);
        if (filenameMatch) {
          filename = filenameMatch[1].replace(/"/g, '');
        }
      }
      
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
    } catch (err) {
      setError('Failed to download search results');
      console.error('View search results error:', err);
    } finally {
      setLoading(prev => ({ ...prev, viewResults: false }));
    }
  };

  const clearSearchSessions = async () => {
    if (!window.confirm('Are you sure you want to clear all search session history? This action cannot be undone.')) {
      return;
    }
    
    try {
      setLoading(prev => ({ ...prev, clearSessions: true }));
      const response = await apiClient.delete('/phase4/search/search-sessions');
      setSearchSessions([]);
      alert(`Cleared ${response.data.cleared_sessions} search sessions`);
    } catch (err) {
      setError('Failed to clear search sessions');
      console.error('Clear search sessions error:', err);
    } finally {
      setLoading(prev => ({ ...prev, clearSessions: false }));
    }
  };

  const deleteSearchSession = async (sessionId: string) => {
    if (!window.confirm(`Are you sure you want to delete search session ${sessionId}?`)) {
      return;
    }
    
    try {
      await apiClient.delete(`/phase4/search/search-sessions/${sessionId}`);
      setSearchSessions(prev => prev.filter(s => s.session_id !== sessionId));
    } catch (err) {
      setError('Failed to delete search session');
      console.error('Delete search session error:', err);
    }
  };

  const setupProgressTracking = (operationId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(`http://localhost:8000/api/v1/phase4/search/progress-stream/${operationId}`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
          case 'connected':
            console.log('SSE connected for operation:', operationId);
            break;
          
          case 'scan_progress':
          case 'search_progress':
            setProgress({
              progress: data.progress || 0,
              current_collection: data.current_collection,
              collections_processed: data.collections_processed,
              total_collections: data.total_collections,
              current_statute: data.current_statute,
              processed_count: data.processed_count
            });
            break;
          
          case 'scan_completed':
            setScanResults(data.results);
            setCurrentOperation(prev => prev ? { ...prev, status: 'completed' } : null);
            setProgress({ progress: 100 });
            setSuccessMessage('Scan completed successfully!');
            eventSource.close();
            break;
          
          case 'search_completed':
            setCurrentOperation(prev => prev ? { ...prev, status: 'completed' } : null);
            setProgress({ progress: 100 });
            setSuccessMessage(`AI search completed! Session ID: ${data.session_id}`);
            fetchSearchSessions(); // Refresh sessions
            eventSource.close();
            break;
          
          case 'scan_error':
          case 'search_error':
            setCurrentOperation(prev => prev ? { ...prev, status: 'error' } : null);
            setError(data.error || 'Operation failed');
            eventSource.close();
            break;
          
          case 'operation_stopped':
            setCurrentOperation(prev => prev ? { ...prev, status: 'stopped' } : null);
            setSuccessMessage('Operation stopped successfully');
            eventSource.close();
            break;
        }
      } catch (err) {
        console.error('SSE parsing error:', err);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      eventSource.close();
    };
  };

  const startScanMissingDates = async () => {
    try {
      setLoading(prev => ({ ...prev, scan: true }));
      setError(null);
      
      const response = await apiClient.post('/phase4/search/scan-missing-dates', {
        collections: selectedCollections.length > 0 ? selectedCollections : null
      });
      
      const scanId = response.data.scan_id;
      setCurrentOperation({ type: 'scan', id: scanId, status: 'running' });
      setProgress({ progress: 0 });
      
      // Setup progress tracking
      setupProgressTracking(scanId);
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start scan');
      console.error('Start scan error:', err);
    } finally {
      setLoading(prev => ({ ...prev, scan: false }));
    }
  };

  const exportMissingDates = async () => {
    try {
      setLoading(prev => ({ ...prev, export: true }));
      setError(null);
      
      const response = await apiClient.post('/phase4/search/export-missing-dates', {
        collections: selectedCollections.length > 0 ? selectedCollections : null
      }, {
        responseType: 'blob'
      });
      
      // Create download link
      const blob = new Blob([response.data], { 
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      // Extract filename from Content-Disposition header or use default
      const contentDisposition = response.headers['content-disposition'];
      let filename = `missing_dates_${new Date().toISOString().split('T')[0]}.xlsx`; // fallback
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename=([^;]+)/);
        if (filenameMatch) {
          filename = filenameMatch[1].replace(/"/g, ''); // remove quotes
        }
      }
      
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      setSuccessMessage('Excel file downloaded successfully!');
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to export missing dates');
      console.error('Export error:', err);
    } finally {
      setLoading(prev => ({ ...prev, export: false }));
    }
  };

  const startAISearch = async () => {
    try {
      setLoading(prev => ({ ...prev, aiSearch: true }));
      setError(null);
      
      const response = await apiClient.post('/phase4/search/search-dates-ai', {
        collections: selectedCollections.length > 0 ? selectedCollections : null,
        use_ai: true
        // max_documents removed - process all missing dates like reference implementation
      });
      
      const searchId = response.data.search_id;
      setCurrentOperation({ type: 'search', id: searchId, status: 'running' });
      setProgress({ progress: 0 });
      
      // Setup progress tracking
      setupProgressTracking(searchId);
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start AI search');
      console.error('Start AI search error:', err);
    } finally {
      setLoading(prev => ({ ...prev, aiSearch: false }));
    }
  };

  const stopCurrentOperation = async () => {
    if (!currentOperation) return;
    
    try {
      setLoading(prev => ({ ...prev, stop: true }));
      await apiClient.post(`/phase4/search/stop-operation/${currentOperation.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to stop operation');
      console.error('Stop operation error:', err);
    } finally {
      setLoading(prev => ({ ...prev, stop: false }));
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setLoading(prev => ({ ...prev, upload: true }));
      setError(null);
      
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await apiClient.post('/phase4/search/upload-reviewed-excel', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
  setSuccessMessage(`Upload successful! ${response.data.approved_dates} approved dates found.`);
  // Save uploaded file and session id for two-step apply
  setLastUploadedFile(file);
  setLastUploadedSessionId(response.data.session_id || null);
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload file');
      console.error('Upload error:', err);
    } finally {
      setLoading(prev => ({ ...prev, upload: false }));
      // Reset file input
      event.target.value = '';
    }
  };

  const handleApplyApproved = async () => {
    if (!lastUploadedFile) {
      alert('No previously uploaded file found. Please upload a reviewed Excel first.');
      return;
    }

    if (!window.confirm('This will apply approved dates to the source DB. Proceed?')) return;

    try {
      setLoading(prev => ({ ...prev, apply: true }));
      setError(null);
      setApplyResult(null);

      const formData = new FormData();
      formData.append('file', lastUploadedFile);
      if (lastUploadedSessionId) {
        // attach session id as a query param
      }

      const url = lastUploadedSessionId
        ? `/phase4/search/apply-approved-dates?session_id=${encodeURIComponent(lastUploadedSessionId)}`
        : '/phase4/search/apply-approved-dates';

      const response = await apiClient.post(url, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setApplyResult(response.data);
      setSuccessMessage(`Applied: ${response.data.applied}, Failed: ${response.data.failed_count}`);

      // Refresh sessions list after apply
      fetchSearchSessions();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to apply approved dates');
      console.error('Apply error:', err);
    } finally {
      setLoading(prev => ({ ...prev, apply: false }));
    }
  };

  const toggleCollectionSelection = (collection: string) => {
    setSelectedCollections(prev =>
      prev.includes(collection)
        ? prev.filter(c => c !== collection)
        : [...prev, collection]
    );
  };

  const selectAllCollections = () => {
    setSelectedCollections(availableCollections);
  };

  const clearCollections = () => {
    setSelectedCollections([]);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="border-b border-gray-200 pb-4">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Search className="h-6 w-6 text-blue-600" />
          Date Search & Review
        </h2>
        <p className="text-sm text-gray-600 mt-1">
          Find missing dates, export for review, and manage AI-powered date extraction
        </p>
      </div>

      {/* Success Message */}
      {successMessage && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-2">
          <CheckCircle className="h-5 w-5 text-green-600" />
          <span className="text-green-800">{successMessage}</span>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-red-600" />
          <span className="text-red-800">{error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-auto text-red-600 hover:text-red-800"
          >
            ×
          </button>
        </div>
      )}

      {/* Collections Selection */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-3">Select Collections</h3>
        <div className="flex gap-2 mb-3">
          <button
            onClick={selectAllCollections}
            className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
          >
            Select All
          </button>
          <button
            onClick={clearCollections}
            className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
          >
            Clear All
          </button>
          <span className="text-sm text-gray-600 py-1">
            {selectedCollections.length} of {availableCollections.length} selected
          </span>
        </div>
        <div className="grid grid-cols-4 gap-2 max-h-32 overflow-y-auto">
          {availableCollections.map(collection => (
            <label key={collection} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedCollections.includes(collection)}
                onChange={() => toggleCollectionSelection(collection)}
                className="rounded border-gray-300"
              />
              <span className="text-sm">{collection}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Current Operation Progress */}
      {currentOperation && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold text-blue-900">
              {currentOperation.type === 'scan' ? 'Scanning Collections' : 'AI Date Search'} in Progress
            </h3>
            {currentOperation.status === 'running' && (
              <button
                onClick={stopCurrentOperation}
                disabled={loading.stop}
                className="flex items-center gap-2 px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
              >
                <StopCircle className="h-4 w-4" />
                {loading.stop ? 'Stopping...' : 'Stop'}
              </button>
            )}
          </div>
          
          <div className="space-y-2">
            {/* Progress Bar */}
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progress.progress}%` }}
              />
            </div>
            
            {/* Progress Details */}
            <div className="text-sm text-blue-800">
              <div>Progress: {progress.progress.toFixed(1)}%</div>
              {progress.current_collection && (
                <div>Current: {progress.current_collection}</div>
              )}
              {progress.current_statute && (
                <div>Processing: {progress.current_statute}</div>
              )}
              {progress.collections_processed && progress.total_collections && (
                <div>Collections: {progress.collections_processed}/{progress.total_collections}</div>
              )}
              {progress.processed_count && (
                <div>Documents Processed: {progress.processed_count}</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Scan Missing Dates */}
        <button
          onClick={startScanMissingDates}
          disabled={loading.scan || currentOperation?.status === 'running' || selectedCollections.length === 0}
          className="flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading.scan ? (
            <RefreshCw className="h-5 w-5 animate-spin" />
          ) : (
            <Search className="h-5 w-5" />
          )}
          <span>{loading.scan ? 'Scanning...' : 'Scan Missing Dates'}</span>
        </button>

        {/* Export to Excel */}
        <button
          onClick={exportMissingDates}
          disabled={loading.export || currentOperation?.status === 'running' || selectedCollections.length === 0}
          className="flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading.export ? (
            <RefreshCw className="h-5 w-5 animate-spin" />
          ) : (
            <Download className="h-5 w-5" />
          )}
          <span>{loading.export ? 'Exporting...' : 'Export to Excel'}</span>
        </button>

        {/* AI Date Search */}
        <button
          onClick={startAISearch}
          disabled={loading.aiSearch || currentOperation?.status === 'running' || selectedCollections.length === 0}
          className="flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading.aiSearch ? (
            <RefreshCw className="h-5 w-5 animate-spin" />
          ) : (
            <Brain className="h-5 w-5" />
          )}
          <span>{loading.aiSearch ? 'Searching...' : 'AI Date Search'}</span>
        </button>

        {/* Upload Reviewed Excel */}
        <label className="flex items-center justify-center gap-2 px-4 py-3 bg-orange-600 text-white rounded-lg hover:bg-orange-700 cursor-pointer">
          {loading.upload ? (
            <RefreshCw className="h-5 w-5 animate-spin" />
          ) : (
            <Upload className="h-5 w-5" />
          )}
          <span>{loading.upload ? 'Uploading...' : 'Upload Reviewed'}</span>
          <input
            type="file"
            accept=".xlsx,.xls"
            onChange={handleFileUpload}
            disabled={loading.upload}
            className="hidden"
          />
        </label>
        {/* Apply Approved (two-step) */}
        <button
          onClick={handleApplyApproved}
          disabled={loading.apply || !lastUploadedFile}
          className="flex items-center justify-center gap-2 px-4 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading.apply ? (
            <RefreshCw className="h-5 w-5 animate-spin" />
          ) : (
            <CheckCircle className="h-5 w-5" />
          )}
          <span>{loading.apply ? 'Applying...' : 'Apply Approved'}</span>
        </button>
      </div>

      {/* Scan Results */}
      {scanResults && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5" />
            Scan Results
          </h3>
          
          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-gray-50 p-3 rounded">
              <div className="text-2xl font-bold text-gray-900">{scanResults.summary.total_documents.toLocaleString()}</div>
              <div className="text-sm text-gray-600">Total Documents</div>
            </div>
            <div className="bg-red-50 p-3 rounded">
              <div className="text-2xl font-bold text-red-900">{scanResults.summary.documents_missing_dates.toLocaleString()}</div>
              <div className="text-sm text-red-600">Missing Dates</div>
            </div>
            <div className="bg-green-50 p-3 rounded">
              <div className="text-2xl font-bold text-green-900">{scanResults.summary.documents_with_dates.toLocaleString()}</div>
              <div className="text-sm text-green-600">With Dates</div>
            </div>
            <div className="bg-blue-50 p-3 rounded">
              <div className="text-2xl font-bold text-blue-900">{scanResults.summary.missing_percentage.toFixed(1)}%</div>
              <div className="text-sm text-blue-600">Missing Percentage</div>
            </div>
          </div>

          {/* Collection Breakdown */}
          <div className="mb-6">
            <h4 className="font-medium text-gray-900 mb-3">Collection Breakdown</h4>
            <div className="overflow-x-auto">
              <table className="min-w-full border border-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">Collection</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">Total</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">Missing</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">%</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(scanResults.collection_breakdown).map(([collection, data]) => (
                    <tr key={collection} className="border-t border-gray-200">
                      <td className="px-4 py-2 text-sm">{collection}</td>
                      <td className="px-4 py-2 text-sm">{data.total_documents.toLocaleString()}</td>
                      <td className="px-4 py-2 text-sm text-red-600">{data.missing_dates.toLocaleString()}</td>
                      <td className="px-4 py-2 text-sm">{data.missing_percentage.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Sample Missing Documents */}
          {scanResults.sample_missing.length > 0 && (
            <div>
              <h4 className="font-medium text-gray-900 mb-3">Sample Missing Documents</h4>
              <div className="space-y-2">
                {scanResults.sample_missing.slice(0, 5).map((doc, index) => (
                  <div key={index} className="bg-gray-50 p-3 rounded text-sm">
                    <div className="font-medium">{doc.Statute_Name}</div>
                    <div className="text-gray-600">{doc.Province} • {doc.collection}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Search Sessions */}
      {searchSessions.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Eye className="h-5 w-5" />
              Recent Search Sessions
            </h3>
            <div className="flex gap-2">
              <button
                onClick={clearSearchSessions}
                disabled={loading.clearSessions}
                className="flex items-center gap-2 px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-50"
              >
                {loading.clearSessions ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <AlertCircle className="h-4 w-4" />
                )}
                Clear All
              </button>
              <button
                onClick={fetchSearchSessions}
                className="flex items-center gap-2 px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
              >
                <RefreshCw className="h-4 w-4" />
                Refresh
              </button>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="min-w-full border border-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">Session ID</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">Created</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">Status</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">Documents</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">AI Processed</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">High Confidence</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">Actions</th>
                </tr>
              </thead>
              <tbody>
                {searchSessions.slice(0, 10).map((session) => (
                  <tr key={session.session_id} className="border-t border-gray-200">
                        <td className="px-4 py-2 text-sm font-mono">{session.session_label || session.session_id}</td>
                        <td className="px-4 py-2 text-sm">{session.created_at_local || session.created_at}</td>
                    <td className="px-4 py-2 text-sm">
                      <span className={`px-2 py-1 rounded text-xs ${
                        session.status === 'completed' ? 'bg-green-100 text-green-800' :
                        session.status === 'pending_review' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {session.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm">{session.total_documents}</td>
                    <td className="px-4 py-2 text-sm">{session.metadata.ai_processed}</td>
                    <td className="px-4 py-2 text-sm">{session.metadata.high_confidence}</td>
                    <td className="px-4 py-2 text-sm">
                      <div className="flex gap-1">
                        <button
                          onClick={() => viewSearchResults(session.session_id)}
                          disabled={loading.viewResults}
                          className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50 flex items-center gap-1"
                          title="Download AI search results as Excel file"
                        >
                          <FileSpreadsheet className="h-3 w-3" />
                          Excel
                        </button>
                        <button
                          onClick={() => deleteSearchSession(session.session_id)}
                          className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
                          title="Delete this session"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default DateSearchTab;
