import React, { useState } from 'react';
import { Database, Wifi, WifiOff, Settings, TestTube } from 'lucide-react';
import axios from 'axios';

interface DatabaseConnectionProps {
  onConnectionUpdate: (info: any) => void;
}

interface ConnectionConfig {
  host: string;
  port: string;
  database: string;
  collection: string;
}

const DatabaseConnection: React.FC<DatabaseConnectionProps> = ({ onConnectionUpdate }) => {
  const [config, setConfig] = useState<ConnectionConfig>({
    host: 'localhost',
    port: '27017',
    database: 'Statutes',
    collection: 'raw_statutes'
  });
  
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionResult, setConnectionResult] = useState<any>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleConfigChange = (field: keyof ConnectionConfig, value: string) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  const testConnection = async () => {
    setIsConnecting(true);
    setConnectionResult(null);
    
    try {
      const response = await axios.get('/api/v1/phase1/connect');
      setConnectionResult(response.data);
      onConnectionUpdate({
        status: 'connected',
        database: response.data.database,
        collection: response.data.collection,
        document_count: response.data.document_count
      });
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Connection failed';
      setConnectionResult({ error: errorMessage });
      onConnectionUpdate({
        status: 'error',
        error: errorMessage
      });
    } finally {
      setIsConnecting(false);
    }
  };

  const getConnectionStatusColor = () => {
    if (connectionResult?.error) return 'text-red-600';
    if (connectionResult?.status === 'connected') return 'text-green-600';
    return 'text-gray-600';
  };

  const getConnectionStatusIcon = () => {
    if (connectionResult?.error) return <WifiOff className="w-5 h-5" />;
    if (connectionResult?.status === 'connected') return <Wifi className="w-5 h-5" />;
    return <Database className="w-5 h-5" />;
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border">
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <Database className="w-5 h-5 text-primary-600" />
          <h2 className="text-lg font-semibold text-gray-900">Database Connection</h2>
        </div>
        <p className="text-sm text-gray-600 mt-1">
          Connect to MongoDB database for data analysis
        </p>
      </div>
      
      <div className="p-6">
        {/* Basic Configuration */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div>
            <label htmlFor="host" className="block text-sm font-medium text-gray-700 mb-1">
              Host
            </label>
            <input
              type="text"
              id="host"
              value={config.host}
              onChange={(e) => handleConfigChange('host', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              placeholder="localhost"
            />
          </div>
          
          <div>
            <label htmlFor="port" className="block text-sm font-medium text-gray-700 mb-1">
              Port
            </label>
            <input
              type="text"
              id="port"
              value={config.port}
              onChange={(e) => handleConfigChange('port', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              placeholder="27017"
            />
          </div>
          
          <div>
            <label htmlFor="database" className="block text-sm font-medium text-gray-700 mb-1">
              Database
            </label>
            <input
              type="text"
              id="database"
              value={config.database}
              onChange={(e) => handleConfigChange('database', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              placeholder="Statutes"
            />
          </div>
          
          <div>
            <label htmlFor="collection" className="block text-sm font-medium text-gray-700 mb-1">
              Collection
            </label>
            <input
              type="text"
              id="collection"
              value={config.collection}
              onChange={(e) => handleConfigChange('collection', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              placeholder="raw_statutes"
            />
          </div>
        </div>

        {/* Advanced Configuration Toggle */}
        <div className="mb-6">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
          >
            <Settings className="w-4 h-4 mr-2" />
            {showAdvanced ? 'Hide' : 'Show'} Advanced Options
          </button>
        </div>

        {/* Advanced Configuration */}
        {showAdvanced && (
          <div className="mb-6 p-4 bg-gray-50 rounded-md">
            <h4 className="text-sm font-medium text-gray-900 mb-3">Advanced Connection Options</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-700 mb-1">
                  Connection String
                </label>
                <input
                  type="text"
                  value={`mongodb://${config.host}:${config.port}/${config.database}`}
                  readOnly
                  className="w-full px-3 py-2 bg-gray-100 border border-gray-300 rounded-md text-sm text-gray-600"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">
                  Timeout (ms)
                </label>
                <input
                  type="number"
                  defaultValue="5000"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                  placeholder="5000"
                />
              </div>
            </div>
          </div>
        )}

        {/* Connection Actions */}
        <div className="flex items-center space-x-4">
          <button
            onClick={testConnection}
            disabled={isConnecting}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200"
          >
            {isConnecting ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Connecting...
              </>
            ) : (
              <>
                <TestTube className="w-4 h-4 mr-2" />
                Test Connection
              </>
            )}
          </button>
          
          <button
            onClick={() => setConfig({
              host: 'localhost',
              port: '27017',
              database: 'Statutes',
              collection: 'raw_statutes'
            })}
            className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-colors duration-200"
          >
            Reset to Defaults
          </button>
        </div>

        {/* Connection Result */}
        {connectionResult && (
          <div className={`mt-6 p-4 rounded-md border ${connectionResult.error ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`}>
            <div className="flex items-start">
              <div className={`flex-shrink-0 ${getConnectionStatusColor()}`}>
                {getConnectionStatusIcon()}
              </div>
              <div className="ml-3">
                <h3 className={`text-sm font-medium ${getConnectionStatusColor()}`}>
                  {connectionResult.error ? 'Connection Failed' : 'Connection Successful'}
                </h3>
                {connectionResult.error ? (
                  <p className="text-sm text-red-700 mt-1">{connectionResult.error}</p>
                ) : (
                  <div className="text-sm text-green-700 mt-1">
                    <p>Successfully connected to database</p>
                    <ul className="mt-2 space-y-1">
                      <li>• Database: {connectionResult.database}</li>
                      <li>• Collection: {connectionResult.collection}</li>
                      <li>• Documents: {connectionResult.document_count?.toLocaleString() || 'Unknown'}</li>
                      <li>• Timestamp: {new Date(connectionResult.timestamp).toLocaleString()}</li>
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DatabaseConnection;
