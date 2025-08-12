import React, { useState, useEffect } from 'react';
import { Activity, Database, Clock, AlertTriangle, CheckCircle } from 'lucide-react';
import axios from 'axios';

interface ConnectionStatusProps {
  databaseInfo: {
    status: 'connected' | 'disconnected' | 'connecting' | 'error';
    database?: string;
    collection?: string;
    document_count?: number;
    error?: string;
  };
  lastRefresh: Date | null;
}

interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  response_time_ms?: number;
  server_version?: string;
  database_size_bytes?: number;
  collections?: number;
  error?: string;
}

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ databaseInfo, lastRefresh }) => {
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);

  const checkHealth = async () => {
    if (databaseInfo.status !== 'connected') return;
    
    setIsCheckingHealth(true);
    try {
      const response = await axios.get('/api/v1/phase1/health');
      setHealthStatus(response.data);
    } catch (error: any) {
      setHealthStatus({
        status: 'unhealthy',
        error: error.response?.data?.detail || error.message || 'Health check failed'
      });
    } finally {
      setIsCheckingHealth(false);
    }
  };

  useEffect(() => {
    if (databaseInfo.status === 'connected' && lastRefresh) {
      checkHealth();
    }
  }, [databaseInfo.status, lastRefresh]);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getHealthStatusColor = () => {
    if (!healthStatus) return 'text-gray-500';
    return healthStatus.status === 'healthy' ? 'text-green-600' : 'text-red-600';
  };

  const getHealthStatusIcon = () => {
    if (!healthStatus) return <Activity className="w-5 h-5" />;
    return healthStatus.status === 'healthy' ? 
      <CheckCircle className="w-5 h-5" /> : 
      <AlertTriangle className="w-5 h-5" />;
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border">
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <Activity className="w-5 h-5 text-primary-600" />
          <h2 className="text-lg font-semibold text-gray-900">Connection Status</h2>
        </div>
        <p className="text-sm text-gray-600 mt-1">
          Database health and performance metrics
        </p>
      </div>
      
      <div className="p-6 space-y-4">
        {/* Connection Status */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Status:</span>
          <div className="flex items-center space-x-2">
            {databaseInfo.status === 'connected' ? (
              <CheckCircle className="w-4 h-4 text-green-500" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-red-500" />
            )}
            <span className={`text-sm font-medium ${
              databaseInfo.status === 'connected' ? 'text-green-600' : 'text-red-600'
            }`}>
              {databaseInfo.status === 'connected' ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>

        {/* Database Info */}
        {databaseInfo.database && (
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">Database:</span>
            <span className="text-sm text-gray-900">{databaseInfo.database}</span>
          </div>
        )}

        {databaseInfo.collection && (
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">Collection:</span>
            <span className="text-sm text-gray-900">{databaseInfo.collection}</span>
          </div>
        )}

        {databaseInfo.document_count !== undefined && (
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">Documents:</span>
            <span className="text-sm text-gray-900">
              {databaseInfo.document_count.toLocaleString()}
            </span>
          </div>
        )}

        {/* Last Refresh */}
        {lastRefresh && (
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">Last Updated:</span>
            <div className="flex items-center space-x-1">
              <Clock className="w-3 h-3 text-gray-400" />
              <span className="text-sm text-gray-900">
                {lastRefresh.toLocaleTimeString()}
              </span>
            </div>
          </div>
        )}

        {/* Health Status */}
        {databaseInfo.status === 'connected' && (
          <>
            <div className="border-t pt-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-700">Health Status:</span>
                <div className="flex items-center space-x-2">
                  {getHealthStatusIcon()}
                  <span className={`text-sm font-medium ${getHealthStatusColor()}`}>
                    {healthStatus?.status === 'healthy' ? 'Healthy' : 'Unhealthy'}
                  </span>
                </div>
              </div>

              {healthStatus && (
                <div className="space-y-2">
                  {healthStatus.response_time_ms && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-600">Response Time:</span>
                      <span className="text-xs text-gray-900">
                        {healthStatus.response_time_ms}ms
                      </span>
                    </div>
                  )}

                  {healthStatus.server_version && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-600">Server Version:</span>
                      <span className="text-xs text-gray-900">
                        {healthStatus.server_version}
                      </span>
                    </div>
                  )}

                  {healthStatus.database_size_bytes && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-600">Database Size:</span>
                      <span className="text-xs text-gray-900">
                        {formatBytes(healthStatus.database_size_bytes)}
                      </span>
                    </div>
                  )}

                  {healthStatus.collections && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-600">Collections:</span>
                      <span className="text-xs text-gray-900">
                        {healthStatus.collections}
                      </span>
                    </div>
                  )}

                  {healthStatus.error && (
                    <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded">
                      <p className="text-xs text-red-700">{healthStatus.error}</p>
                    </div>
                  )}
                </div>
              )}

              <button
                onClick={checkHealth}
                disabled={isCheckingHealth}
                className="mt-3 w-full inline-flex items-center justify-center px-3 py-2 border border-gray-300 shadow-sm text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200"
              >
                {isCheckingHealth ? (
                  <>
                    <Activity className="w-3 h-3 mr-1 animate-spin" />
                    Checking...
                  </>
                ) : (
                  <>
                    <Activity className="w-3 h-3 mr-1" />
                    Check Health
                  </>
                )}
              </button>
            </div>
          </>
        )}

        {/* Error Display */}
        {databaseInfo.error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded">
            <div className="flex items-start space-x-2">
              <AlertTriangle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-red-800">Connection Error</p>
                <p className="text-sm text-red-700 mt-1">{databaseInfo.error}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ConnectionStatus;
