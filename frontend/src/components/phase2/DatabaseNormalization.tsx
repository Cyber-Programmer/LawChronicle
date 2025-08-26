import React, { useState, useEffect } from 'react';
import { Play, RotateCcw, Eye, Download, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import axios from 'axios';

interface DatabaseNormalizationProps {
  config: any;
  onStatusUpdate?: () => void;
  onConfigUpdate?: (updates: any) => void;
}

interface NormalizationConfig {
  mongo_uri: string;
  source_db: string;
  source_collection: string;
  target_db: string;
  target_collection: string;
}

interface DatabaseInfo {
  databases: string[];
  collections: { [key: string]: string[] };
}

interface NormalizationResult {
  success: boolean;
  script_name: string;
  stdout: string;
  stderr: string;
  return_code: number;
  executed_at: string;
  error?: string;
}

const DatabaseNormalization: React.FC<DatabaseNormalizationProps> = ({ config: propConfig, onStatusUpdate, onConfigUpdate }) => {
  const [config, setConfig] = useState<NormalizationConfig>({
    mongo_uri: propConfig?.mongo_uri || 'mongodb://localhost:27017',
    source_db: propConfig?.source_db || 'Statutes',
    source_collection: propConfig?.source_collection || 'raw_statutes',
    target_db: propConfig?.target_db || 'Statutes',
    target_collection: propConfig?.target_collection || 'normalized_statutes'
  });
  
  const [isRunning, setIsRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState<string>('');
  const [progress, setProgress] = useState<number>(0);
  const [results, setResults] = useState<NormalizationResult[]>([]);
  const [error, setError] = useState<string>('');
  const [showConfig, setShowConfig] = useState(true);
  const [testResults, setTestResults] = useState<any>(null);
  const [connectionTest, setConnectionTest] = useState<any>(null);
  const [debugScript, setDebugScript] = useState<any>(null);
  const [showRollbackConfirm, setShowRollbackConfirm] = useState(false);
  const [databaseInfo, setDatabaseInfo] = useState<DatabaseInfo>({ databases: [], collections: {} });
  const [isLoadingDatabases, setIsLoadingDatabases] = useState(false);
  const [showNewCollectionModal, setShowNewCollectionModal] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState('');
  const [newCollectionType, setNewCollectionType] = useState<'source' | 'target'>('source');
  const [showNewDatabaseModal, setShowNewDatabaseModal] = useState(false);
  const [newDatabaseName, setNewDatabaseName] = useState('');
  const [logicTestResults, setLogicTestResults] = useState<any>(null);
  const [configSaved, setConfigSaved] = useState(false);

  const handleConfigChange = (field: keyof NormalizationConfig, value: string) => {
    const newConfig = {
      ...config,
      [field]: value
    };
    
    setConfig(newConfig);
    localStorage.setItem('dbNormConfig', JSON.stringify(newConfig));
    // Update parent configuration
    if (onConfigUpdate) {
      onConfigUpdate({ [field]: value });
    }
    
    // Show saved indicator
    setConfigSaved(true);
    setTimeout(() => setConfigSaved(false), 2000);
    
    // Also update the parent config if onStatusUpdate is available
    if (onStatusUpdate) {
      onStatusUpdate();
    }
  };

  const fetchDatabases = async () => {
    try {
      setIsLoadingDatabases(true);
      const response = await axios.get('/api/v1/phase2/databases');
      if (response.data.success) {
        const databases = response.data.databases;
        setDatabaseInfo(prev => ({ ...prev, databases }));
        
        // Fetch collections for each database
        const collections: { [key: string]: string[] } = {};
        for (const dbName of databases) {
          try {
            const collResponse = await axios.get(`/api/v1/phase2/collections/${dbName}`);
            if (collResponse.data.success) {
              collections[dbName] = collResponse.data.collections;
            }
          } catch (err) {
            console.warn(`Failed to fetch collections for ${dbName}:`, err);
            collections[dbName] = [];
          }
        }
        setDatabaseInfo(prev => ({ ...prev, collections }));
      }
    } catch (err: any) {
      console.error('Failed to fetch databases:', err);
    } finally {
      setIsLoadingDatabases(false);
    }
  };

  const refreshCollections = async (databaseName: string) => {
    try {
      const response = await axios.get(`/api/v1/phase2/collections/${databaseName}`);
      if (response.data.success) {
        setDatabaseInfo(prev => ({
          ...prev,
          collections: {
            ...prev.collections,
            [databaseName]: response.data.collections
          }
        }));
      }
    } catch (err: any) {
      console.error(`Failed to refresh collections for ${databaseName}:`, err);
    }
  };

  const handleDatabaseChange = async (field: 'source_db' | 'target_db', value: string) => {
    setConfig(prev => ({
      ...prev,
      [field]: value
    }));
    
    // Reset collection if database changes
    if (field === 'source_db') {
      setConfig(prev => ({ ...prev, source_collection: '' }));
    } else {
      setConfig(prev => ({ ...prev, target_collection: '' }));
    }
  };

  const handleNewCollection = async () => {
    if (newCollectionName.trim()) {
      try {
        // Create the collection in MongoDB
        const response = await axios.post('/api/v1/phase2/create-collection', {
          database: newCollectionType === 'source' ? config.source_db : config.target_db,
          collection_name: newCollectionName.trim()
        });
        
        if (response.data.success) {
          // Update local config
          if (newCollectionType === 'source') {
            setConfig(prev => ({ ...prev, source_collection: newCollectionName.trim() }));
          } else {
            setConfig(prev => ({ ...prev, target_collection: newCollectionName.trim() }));
          }
          
          // Refresh collections for the relevant database
          if (newCollectionType === 'source') {
            await refreshCollections(config.source_db);
          } else {
            await refreshCollections(config.target_db);
          }
          
          setNewCollectionName('');
          setShowNewCollectionModal(false);
        } else {
          throw new Error(response.data.message || 'Failed to create collection');
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || err.message || 'Failed to create collection');
      }
    }
  };

  const handleNewDatabase = async () => {
    if (newDatabaseName.trim()) {
      try {
        // Create the database in MongoDB
        const response = await axios.post('/api/v1/phase2/create-database', {
          database_name: newDatabaseName.trim()
        });
        
        if (response.data.success) {
          // Refresh databases list
          await fetchDatabases();
          
          setNewDatabaseName('');
          setShowNewDatabaseModal(false);
        } else {
          throw new Error(response.data.message || 'Failed to create database');
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || err.message || 'Failed to create database');
      }
    }
  };

  useEffect(() => {
    fetchDatabases();
  }, []);

  // Update local config when propConfig changes
useEffect(() => {
  const savedConfig = localStorage.getItem('dbNormConfig');
  if (savedConfig) {
    setConfig(JSON.parse(savedConfig));
  } else if (propConfig) {
    setConfig({
      mongo_uri: propConfig.mongo_uri || 'mongodb://localhost:27017',
      source_db: propConfig.source_db || 'Statutes',
      source_collection: propConfig.source_collection || 'raw_statutes',
      target_db: propConfig.target_db || 'Statutes',
      target_collection: propConfig.target_collection || 'normalized_statutes'
    });
  }
}, [propConfig]);

  const testConnection = async () => {
    try {
      setError('');
      setConnectionTest(null);
      setCurrentStep('Testing MongoDB connection...');
      
      const response = await axios.post('/api/v1/phase2/test-connection');
      
      if (response.data.success) {
        setConnectionTest(response.data);
        setCurrentStep('Connection test completed successfully!');
      } else {
        throw new Error(response.data.message || 'Connection test failed');
      }
      
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Connection test failed');
      setCurrentStep('');
    }
  };

  const generateDebugScript = async () => {
    try {
      setError('');
      setDebugScript(null);
      setCurrentStep('Generating debug script...');
      
      const response = await axios.post('/api/v1/phase2/debug-script', config);
      
      if (response.data.success) {
        setDebugScript(response.data);
        setCurrentStep('Debug script generated successfully!');
      } else {
        throw new Error(response.data.message || 'Debug script generation failed');
      }
      
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Debug script generation failed');
      setCurrentStep('');
    }
  };

  const testNormalization = async () => {
    try {
      setError('');
      setTestResults(null);
      setCurrentStep('Testing normalization with sample data...');
      
      const response = await axios.post('/api/v1/phase2/test-normalization', config);
      
      if (response.data.success) {
        setTestResults(response.data);
        setCurrentStep('Test completed successfully!');
      } else {
        throw new Error(response.data.message || 'Test failed');
      }
      
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Test failed');
      setCurrentStep('');
    }
  };

  const testNormalizationLogic = async () => {
    try {
      setLogicTestResults(null);
      const response = await axios.post('/api/v1/phase2/test-normalization-logic');
      if (response.data.success) {
        setLogicTestResults(response.data);
      }
    } catch (err: any) {
      console.error('Failed to test normalization logic:', err);
      setLogicTestResults({ error: err.message });
    }
  };

  const startNormalization = async () => {
    setIsRunning(true);
    setError('');
    setResults([]);
    setProgress(0);
    setCurrentStep('Initializing...');

    try {
      // Step 1: Generate scripts
      setCurrentStep('Generating normalization scripts...');
      setProgress(10);
      
      const scriptsResponse = await axios.post('/api/v1/phase2/generate-scripts', config);
      if (!scriptsResponse.data.success) {
        throw new Error('Failed to generate scripts');
      }

      // Step 2: Execute normalization using service architecture
      setCurrentStep('Executing normalization process...');
      setProgress(30);
      
      const serviceRequest = {
        metadata: {
          source_database: config.source_db,
          target_database: config.target_db,
          overwrite_existing: true
        }
      };
      
      const normalizationResponse = await axios.post('/api/v1/phase2/start-normalization', serviceRequest);
      
      if (normalizationResponse.data.success) {
        setResults(normalizationResponse.data.results);
        setProgress(100);
        setCurrentStep('Normalization completed successfully!');
        
        // Update status in parent component
        if (onStatusUpdate) {
          onStatusUpdate();
        }
      } else {
        throw new Error(normalizationResponse.data.message || 'Normalization failed');
      }
      
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'An error occurred during normalization');
      setCurrentStep('Normalization failed');
    } finally {
      setIsRunning(false);
    }
  };

  const handleRollbackClick = () => {
    setShowRollbackConfirm(true);
  };

  const rollbackNormalization = async () => {
    try {
      setError('');
      setCurrentStep('Rolling back changes...');
      
      const response = await axios.post('/api/v1/phase2/rollback');
      
      if (response.data.success) {
        setResults([]);
        setProgress(0);
        setCurrentStep('Rollback completed successfully');
        
        // Update status in parent component
        if (onStatusUpdate) {
          onStatusUpdate();
        }
      } else {
        throw new Error('Rollback failed');
      }
      
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Rollback failed');
    } finally {
      setCurrentStep('');
      setShowRollbackConfirm(false);
    }
  };

  const getStepStatus = (stepName: string) => {
    const result = results.find(r => r.script_name === stepName);
    if (!result) return 'pending';
    return result.success ? 'success' : 'failed';
  };

  const getStepIcon = (stepName: string) => {
    const status = getStepStatus(stepName);
    switch (status) {
      case 'success':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <AlertTriangle className="h-5 w-5 text-red-500" />;
      case 'pending':
        return <Clock className="h-5 w-5 text-gray-400" />;
      default:
        return <Clock className="h-5 w-5 text-gray-400" />;
    }
  };

  const getStepColor = (stepName: string) => {
    const status = getStepStatus(stepName);
    switch (status) {
      case 'success':
        return 'bg-green-50 border-green-200';
      case 'failed':
        return 'bg-red-50 border-red-200';
      case 'pending':
        return 'bg-gray-50 border-gray-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  // Export configuration to JSON file
  const exportConfig = () => {
    const configData = {
      ...config,
      exported_at: new Date().toISOString(),
      version: '1.0'
    };
    
    const blob = new Blob([JSON.stringify(configData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lawchronicle_config_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Import configuration from JSON file
  const importConfig = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const importedConfig = JSON.parse(e.target?.result as string);
        
        // Validate and merge configuration
        const validConfig = {
          mongo_uri: importedConfig.mongo_uri || config.mongo_uri,
          source_db: importedConfig.source_db || config.source_db,
          source_collection: importedConfig.source_collection || config.source_collection,
          target_db: importedConfig.target_db || config.target_db,
          target_collection: importedConfig.target_collection || config.target_collection
        };
        
        setConfig(validConfig);
        
        // Update parent configuration
        if (onConfigUpdate) {
          onConfigUpdate(validConfig);
        }
        
        setConfigSaved(true);
        setTimeout(() => setConfigSaved(false), 2000);
        
      } catch (error) {
        alert('Invalid configuration file. Please check the format.');
      }
    };
    reader.readAsText(file);
    
    // Reset file input
    event.target.value = '';
  };

  return (
    <div className="space-y-6">
      {/* Configuration Panel */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">Normalization Configuration</h2>
          <div className="flex items-center space-x-3">
            {isLoadingDatabases && (
              <div className="flex items-center text-sm text-gray-500">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600 mr-2"></div>
                Loading databases...
              </div>
            )}
            <div className="flex items-center space-x-2">
              <button
                onClick={exportConfig}
                className="px-3 py-1 text-sm text-blue-600 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                title="Export configuration"
              >
                📤 Export
              </button>
              <label className="px-3 py-1 text-sm text-green-600 bg-green-50 border border-green-200 rounded-md hover:bg-green-100 focus:outline-none focus:ring-2 focus:ring-green-500 cursor-pointer">
                📥 Import
                <input
                  type="file"
                  accept=".json"
                  onChange={importConfig}
                  className="hidden"
                />
              </label>
            </div>
          </div>
        </div>
        
                 {showConfig && (
           <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
             <div>
               <label className="block text-sm font-medium text-gray-700 mb-1">
                 MongoDB URI
               </label>
               <input
                 type="text"
                 value={config.mongo_uri}
                 onChange={(e) => handleConfigChange('mongo_uri', e.target.value)}
                 className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                 placeholder="mongodb://localhost:27017"
               />
             </div>
             
             <div>
               <label className="block text-sm font-medium text-gray-700 mb-1">
                 Source Database
               </label>
               <div className="flex space-x-2">
                 <select
                   value={config.source_db}
                   onChange={(e) => handleDatabaseChange('source_db', e.target.value)}
                   className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                   disabled={isLoadingDatabases}
                 >
                   <option value="">Select Database</option>
                   {databaseInfo.databases.map((db) => (
                     <option key={db} value={db}>{db}</option>
                   ))}
                 </select>
                 <button
                   onClick={() => fetchDatabases()}
                   disabled={isLoadingDatabases}
                   className="px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500"
                   title="Refresh databases"
                 >
                   🔄
                 </button>
                 <button
                   onClick={() => setShowNewDatabaseModal(true)}
                   disabled={isLoadingDatabases}
                   className="px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500"
                   title="Create new database"
                 >
                   ➕
                 </button>
               </div>
             </div>
             
             <div>
               <label className="block text-sm font-medium text-gray-700 mb-1">
                 Source Collection
               </label>
                                <div className="flex space-x-2">
                   <select
                     value={config.source_collection}
                     onChange={(e) => handleConfigChange('source_collection', e.target.value)}
                     className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                     disabled={!config.source_db || isLoadingDatabases}
                   >
                     <option value="">Select Collection</option>
                     {config.source_db && databaseInfo.collections[config.source_db]?.map((coll) => (
                       <option key={coll} value={coll}>{coll}</option>
                     ))}
                   </select>
                   <button
                     onClick={() => {
                       if (config.source_db) {
                         refreshCollections(config.source_db);
                       }
                     }}
                     disabled={!config.source_db || isLoadingDatabases}
                     className="px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500"
                     title="Refresh collections"
                   >
                     🔄
                   </button>
                   <button
                     onClick={() => {
                       setNewCollectionType('source');
                       setShowNewCollectionModal(true);
                     }}
                     className="px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500"
                     title="Create new collection"
                   >
                     ➕
                 </button>
               </div>
               <p className="text-xs text-gray-500 mt-1">Input collection containing raw statute data</p>
             </div>
             
             <div>
               <label className="block text-sm font-medium text-gray-700 mb-1">
                 Target Database
               </label>
               <div className="flex space-x-2">
                 <select
                   value={config.target_db}
                   onChange={(e) => handleDatabaseChange('target_db', e.target.value)}
                   className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                   disabled={isLoadingDatabases}
                 >
                   <option value="">Select Database</option>
                   {databaseInfo.databases.map((db) => (
                     <option key={db} value={db}>{db}</option>
                   ))}
                 </select>
                 <button
                   onClick={() => fetchDatabases()}
                   disabled={isLoadingDatabases}
                   className="px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500"
                   title="Refresh databases"
                 >
                   🔄
                 </button>
                 <button
                   onClick={() => setShowNewDatabaseModal(true)}
                   disabled={isLoadingDatabases}
                   className="px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500"
                   title="Create new database"
                 >
                   ➕
                 </button>
               </div>
             </div>

             <div>
               <label className="block text-sm font-medium text-gray-700 mb-1">
                 Target Collection
               </label>
               <div className="flex space-x-2">
                 <select
                   value={config.target_collection}
                   onChange={(e) => handleConfigChange('target_collection', e.target.value)}
                   className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                   disabled={!config.target_db || isLoadingDatabases}
                 >
                   <option value="">Select Collection</option>
                   {config.target_db && databaseInfo.collections[config.target_db]?.map((coll) => (
                     <option key={coll} value={coll}>{coll}</option>
                   ))}
                 </select>
                                    <button
                     onClick={() => {
                       if (config.target_db) {
                         refreshCollections(config.target_db);
                       }
                     }}
                     disabled={!config.target_db || isLoadingDatabases}
                     className="px-2 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500"
                     title="Refresh collections"
                   >
                     🔄
                   </button>
                 <button
                   onClick={() => {
                     setNewCollectionType('target');
                     setShowNewCollectionModal(true);
                   }}
                   className="px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                   title="Create new collection"
                   disabled={!config.target_db}
                 >
                   ➕
                 </button>
               </div>
               <p className="text-xs text-gray-500 mt-1">Output collection for normalized data</p>
             </div>
           </div>
         )}
        
        <div className="flex items-center space-x-4">
          <button
            onClick={testConnection}
            disabled={isRunning}
            className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <CheckCircle className="h-4 w-4 mr-2" />
            Test Connection
          </button>
          
          <button
            onClick={generateDebugScript}
            disabled={isRunning}
            className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download className="h-4 w-4 mr-2" />
            Debug Script
          </button>
          
          <button
            onClick={testNormalization}
            disabled={isRunning}
            className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Eye className="h-4 w-4 mr-2" />
            Test Sample
          </button>

          <button
            onClick={testNormalizationLogic}
            disabled={isRunning}
            className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Eye className="h-4 w-4 mr-2" />
            Test Logic
          </button>
          
          <button
            onClick={startNormalization}
            disabled={isRunning}
            className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play className="h-5 w-5 mr-2" />
            {isRunning ? 'Running...' : 'Start Normalization'}
          </button>
          
          <button
            onClick={handleRollbackClick}
            disabled={isRunning || results.length === 0}
            className="inline-flex items-center px-6 py-3 border border-gray-300 text-base font-medium rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RotateCcw className="h-5 w-5 mr-2" />
            Rollback Changes
          </button>
        </div>
      </div>

      {/* Progress and Status */}
      {isRunning && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Normalization Progress</h3>
          
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">{currentStep}</span>
              <span className="text-sm font-medium text-gray-700">{progress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Normalization Results</h3>
          
          <div className="space-y-4">
            {/* Step 1: Statute Name Normalization */}
            <div className={`p-4 border rounded-lg ${getStepColor('statute_name_normalizer')}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  {getStepIcon('statute_name_normalizer')}
                  <div>
                    <h4 className="font-medium text-gray-900">Statute Name Normalization</h4>
                    <p className="text-sm text-gray-600">Clean and standardize statute names with enhanced logic</p>
                  </div>
                </div>
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                  getStepStatus('statute_name_normalizer') === 'success' 
                    ? 'bg-green-100 text-green-800' 
                    : getStepStatus('statute_name_normalizer') === 'failed'
                    ? 'bg-red-100 text-red-800'
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {getStepStatus('statute_name_normalizer')}
                </span>
              </div>
            </div>

            {/* Step 2: Structure Cleaning */}
            <div className={`p-4 border rounded-lg ${getStepColor('structure_cleaner')}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  {getStepIcon('structure_cleaner')}
                  <div>
                    <h4 className="font-medium text-gray-900">Structure Cleaning</h4>
                    <p className="text-sm text-gray-600">Standardize database schema and field names with enhanced mapping</p>
                  </div>
                </div>
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                  getStepStatus('structure_cleaner') === 'success' 
                    ? 'bg-green-100 text-green-800' 
                    : getStepStatus('structure_cleaner') === 'failed'
                    ? 'bg-red-100 text-red-800'
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {getStepStatus('structure_cleaner')}
                </span>
              </div>
            </div>

            {/* Step 3: Alphabetical Sorting */}
            <div className={`p-4 border rounded-lg ${getStepColor('alphabetical_sorter')}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  {getStepIcon('alphabetical_sorter')}
                  <div>
                    <h4 className="font-medium text-gray-900">Alphabetical Sorting</h4>
                    <p className="text-sm text-gray-600">Sort statutes alphabetically with enhanced year-based grouping</p>
                  </div>
                </div>
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                  getStepStatus('alphabetical_sorter') === 'success' 
                    ? 'bg-green-100 text-green-800' 
                    : getStepStatus('alphabetical_sorter') === 'failed'
                    ? 'bg-red-100 text-red-800'
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {getStepStatus('alphabetical_sorter')}
                </span>
              </div>
            </div>
          </div>

          {/* Detailed Results */}
          <div className="mt-6">
            <h4 className="font-medium text-gray-900 mb-3">Detailed Results</h4>
            <div className="space-y-3">
              {results.map((result, index) => (
                <details key={index} className="border border-gray-200 rounded-lg">
                  <summary className="px-4 py-3 cursor-pointer hover:bg-gray-50 font-medium text-gray-900">
                    {result.script_name} - {result.success ? 'Success' : 'Failed'}
                  </summary>
                  <div className="px-4 pb-3 space-y-2">
                    {result.stdout && (
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-1">Output:</p>
                        <pre className="text-xs bg-gray-100 p-2 rounded overflow-x-auto">{result.stdout}</pre>
                      </div>
                    )}
                    {result.stderr && (
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-1">Errors:</p>
                        <pre className="text-xs bg-red-100 p-2 rounded overflow-x-auto text-red-700">{result.stderr}</pre>
                      </div>
                    )}
                    {result.error && (
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-1">Error:</p>
                        <p className="text-xs text-red-700">{result.error}</p>
                      </div>
                    )}
                    <p className="text-xs text-gray-500">
                      Executed at: {new Date(result.executed_at).toLocaleString()}
                    </p>
                  </div>
                </details>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <AlertTriangle className="h-5 w-5 text-red-400 mr-2" />
            <h3 className="text-sm font-medium text-red-800">Error</h3>
          </div>
          <p className="text-sm text-red-700 mt-1">{error}</p>
        </div>
      )}

      {/* Connection Test Results */}
      {connectionTest && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Connection Test Results</h3>
          <div className={`border rounded-lg p-4 ${connectionTest.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
            <div className="flex items-center">
              {connectionTest.success ? (
                <CheckCircle className="h-5 w-5 text-green-400 mr-2" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-red-400 mr-2" />
              )}
              <p className={`text-sm ${connectionTest.success ? 'text-green-800' : 'text-red-800'}`}>
                {connectionTest.message}
              </p>
            </div>
          </div>
          
          {connectionTest.success && (
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-gray-50 p-3 rounded border">
                <p className="text-sm font-medium text-gray-700">Database</p>
                <p className="text-sm text-gray-900">{connectionTest.database}</p>
              </div>
              <div className="bg-gray-50 p-3 rounded border">
                <p className="text-sm font-medium text-gray-700">Source Collection</p>
                <p className="text-sm text-gray-900">{connectionTest.source_collection}</p>
              </div>
              <div className="bg-gray-50 p-3 rounded border">
                <p className="text-sm font-medium text-gray-700">Document Count</p>
                <p className="text-sm text-gray-900">{connectionTest.source_document_count}</p>
              </div>
              <div className="bg-gray-50 p-3 rounded border">
                <p className="text-sm font-medium text-gray-700">Test Time</p>
                <p className="text-sm text-gray-900">{new Date(connectionTest.tested_at).toLocaleString()}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Debug Script Results */}
      {debugScript && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Debug Script Results</h3>
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
            <p className="text-sm text-green-800">{debugScript.message}</p>
          </div>
          
          <div className="space-y-4">
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Configuration Used</h4>
              <div className="bg-gray-50 p-3 rounded border">
                <pre className="text-xs text-gray-700 overflow-x-auto">
                  {JSON.stringify(debugScript.config, null, 2)}
                </pre>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Generated Script</h4>
              <div className="bg-gray-50 p-3 rounded border">
                <pre className="text-xs text-gray-700 overflow-x-auto whitespace-pre-wrap">
                  {debugScript.script_content}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Test Results */}
      {testResults && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Test Results</h3>
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
            <p className="text-sm text-green-800">{testResults.message}</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Sample Documents (Before)</h4>
              <div className="space-y-2">
                {testResults.sample_documents.map((doc: any, index: number) => (
                  <div key={index} className="text-sm bg-gray-50 p-2 rounded border">
                    <p><strong>Statute Name:</strong> {doc.Statute_Name || 'N/A'}</p>
                    <p><strong>Section:</strong> {doc.Section || 'N/A'}</p>
                    <p><strong>Year:</strong> {doc.Year || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>
            
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Normalized Documents (After)</h4>
              <div className="space-y-2">
                {testResults.normalized_documents.map((doc: any, index: number) => (
                  <div key={index} className="text-sm bg-green-50 p-2 rounded border">
                    <p><strong>Statute Name:</strong> {doc.Statute_Name || 'N/A'}</p>
                    <p><strong>Section Number:</strong> {doc.Section_Number || 'N/A'}</p>
                    <p><strong>Section Definition:</strong> {doc.Section_Definition || 'N/A'}</p>
                    <p><strong>Year:</strong> {doc.Year || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Logic Test Results */}
      {logicTestResults && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Normalization Logic Test Results</h3>
          <div className={`border rounded-lg p-4 ${logicTestResults.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
            <div className="flex items-center">
              {logicTestResults.success ? (
                <CheckCircle className="h-5 w-5 text-green-400 mr-2" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-red-400 mr-2" />
              )}
              <p className={`text-sm ${logicTestResults.success ? 'text-green-800' : 'text-red-800'}`}>
                {logicTestResults.message}
              </p>
            </div>
          </div>
          
          {logicTestResults.success && (
            <div className="mt-4 space-y-4">
              <div className="bg-gray-50 p-3 rounded border">
                <p className="text-sm font-medium text-gray-700">Tested At</p>
                <p className="text-sm text-gray-900">{new Date(logicTestResults.tested_at).toLocaleString()}</p>
              </div>
              
              {/* Name Normalization Results */}
              <div className="bg-gray-50 p-3 rounded border">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Name Normalization Tests</h4>
                <div className="space-y-2">
                  {logicTestResults.name_normalization?.map((test: any, index: number) => (
                    <div key={index} className="text-xs bg-white p-2 rounded border">
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <span className="font-medium">Original:</span> {test.original || 'null'}
                        </div>
                        <div>
                          <span className="font-medium">Normalized:</span> {test.normalized || 'null'}
                        </div>
                      </div>
                      {!test.success && (
                        <div className="text-red-600 mt-1">
                          Error: {test.error}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              
              {/* Section Extraction Results */}
              <div className="bg-gray-50 p-3 rounded border">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Section Extraction Tests</h4>
                <div className="space-y-2">
                  {logicTestResults.section_extraction?.map((test: any, index: number) => (
                    <div key={index} className="text-xs bg-white p-2 rounded border">
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <span className="font-medium">Original:</span> {test.original || 'null'}
                        </div>
                        <div>
                          <span className="font-medium">Extracted:</span> {test.extracted ? `Section ${test.extracted.section_number}: ${test.extracted.definition}` : 'null'}
                        </div>
                      </div>
                      {!test.success && (
                        <div className="text-red-600 mt-1">
                          Error: {test.error}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
          
          {logicTestResults.error && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-sm text-red-800">
                <strong>Error:</strong> {logicTestResults.error}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Information Panel */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-blue-800">Enhanced Normalization Process</h3>
          <div className="flex space-x-2">
            <button
              onClick={testConnection}
              className="inline-flex items-center px-3 py-1 text-xs font-medium rounded border border-blue-300 text-blue-700 bg-blue-100 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <CheckCircle className="h-3 w-3 mr-1" />
              Test Connection
            </button>
            <button
              onClick={generateDebugScript}
              className="inline-flex items-center px-3 py-1 text-xs font-medium rounded border border-blue-300 text-blue-700 bg-blue-100 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <Download className="h-3 w-3 mr-1" />
              Debug Script
            </button>
          </div>
        </div>
        <ul className="text-sm text-blue-700 space-y-1">
          <li>• <strong>Statute Name Normalization:</strong> Enhanced logic for cleaning names, extracting section info, and handling legal prefixes</li>
          <li>• <strong>Structure Cleaning:</strong> Advanced field mapping with support for all schema fields including content and metadata</li>
          <li>• <strong>Alphabetical Sorting:</strong> Smart sorting with year-based grouping within statute name categories</li>
        </ul>
        <p className="text-xs text-blue-600 mt-2">
          The process creates collections: <code>normalized_statutes</code> → <code>sorted_statutes</code>
        </p>
      </div>

      {/* Rollback Confirmation Modal */}
      {showRollbackConfirm && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3 text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
                <AlertTriangle className="h-6 w-6 text-red-600" />
              </div>
              <h3 className="text-lg font-medium text-gray-900 mt-4">Confirm Rollback</h3>
              <div className="mt-2 px-7 py-3">
                <p className="text-sm text-gray-500">
                  Are you sure you want to rollback all normalization changes? This will delete all normalized and sorted collections.
                </p>
              </div>
              <div className="flex justify-center space-x-4 mt-4">
                <button
                  onClick={() => setShowRollbackConfirm(false)}
                  className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-500"
                >
                  Cancel
                </button>
                <button
                  onClick={rollbackNormalization}
                  className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500"
                >
                  Confirm Rollback
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* New Collection Modal */}
      {showNewCollectionModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Create New Collection</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Collection Type
                  </label>
                  <div className="flex space-x-4">
                    <label className="flex items-center">
                      <input
                        type="radio"
                        value="source"
                        checked={newCollectionType === 'source'}
                        onChange={(e) => setNewCollectionType(e.target.value as 'source' | 'target')}
                        className="mr-2"
                      />
                      Source Collection
                    </label>
                    <label className="flex items-center">
                      <input
                        type="radio"
                        value="target"
                        checked={newCollectionType === 'target'}
                        onChange={(e) => setNewCollectionType(e.target.value as 'source' | 'target')}
                        className="mr-2"
                      />
                      Target Collection
                    </label>
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Collection Name
                  </label>
                  <input
                    type="text"
                    value={newCollectionName}
                    onChange={(e) => setNewCollectionName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                    placeholder="Enter collection name"
                    onKeyPress={(e) => e.key === 'Enter' && handleNewCollection()}
                  />
                </div>
                
                <div className="flex justify-end space-x-3">
                  <button
                    onClick={() => {
                      setShowNewCollectionModal(false);
                      setNewCollectionName('');
                    }}
                    className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-500"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleNewCollection}
                    disabled={!newCollectionName.trim()}
                    className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Create Collection
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* New Database Modal */}
      {showNewDatabaseModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Create New Database</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Database Name
                  </label>
                  <input
                    type="text"
                    value={newDatabaseName}
                    onChange={(e) => setNewDatabaseName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                    placeholder="Enter database name"
                    onKeyPress={(e) => e.key === 'Enter' && handleNewDatabase()}
                  />
                </div>
                
                <div className="flex justify-end space-x-3">
                  <button
                    onClick={() => {
                      setShowNewDatabaseModal(false);
                      setNewDatabaseName('');
                    }}
                    className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-500"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleNewDatabase}
                    disabled={!newDatabaseName.trim()}
                    className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Create Database
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Config Saved Indicator */}
      {configSaved && (
        <div className="fixed bottom-4 right-4 bg-green-500 text-white px-4 py-2 rounded-md shadow-lg z-50">
          <CheckCircle className="h-4 w-4 mr-2" />
          Configuration Saved!
        </div>
      )}
    </div>
  );
};

export default DatabaseNormalization;
