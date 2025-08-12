import React, { useState, useEffect } from 'react';
import { Database, BarChart3, FileText, Activity, RefreshCw, AlertCircle, CheckCircle, XCircle } from 'lucide-react';
import DatabaseConnection from '../components/phase1/DatabaseConnection';
import FieldStatistics from '../components/phase1/FieldStatistics';
import SampleDataViewer from '../components/phase1/SampleDataViewer';
import StatuteAnalysis from '../components/phase1/StatuteAnalysis';
import ConnectionStatus from '../components/phase1/ConnectionStatus';

interface DatabaseInfo {
  status: 'connected' | 'disconnected' | 'connecting' | 'error';
  database?: string;
  collection?: string;
  document_count?: number;
  error?: string;
}

const Phase1: React.FC = () => {
  const [databaseInfo, setDatabaseInfo] = useState<DatabaseInfo>({ status: 'disconnected' });
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const handleConnectionUpdate = (info: DatabaseInfo) => {
    setDatabaseInfo(info);
  };

  const handleRefresh = () => {
    setLastRefresh(new Date());
  };

  const getStatusIcon = () => {
    switch (databaseInfo.status) {
      case 'connected':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'connecting':
        return <RefreshCw className="w-5 h-5 text-yellow-500 animate-spin" />;
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />;
      default:
        return <AlertCircle className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusText = () => {
    switch (databaseInfo.status) {
      case 'connected':
        return 'Connected';
      case 'connecting':
        return 'Connecting...';
      case 'error':
        return 'Connection Error';
      default:
        return 'Disconnected';
    }
  };

  const getStatusColor = () => {
    switch (databaseInfo.status) {
      case 'connected':
        return 'text-green-600';
      case 'connecting':
        return 'text-yellow-600';
      case 'error':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-12">
            <div className="flex items-center space-x-3">
              <Database className="w-6 h-6 text-primary-600" />
              <div>
                <h1 className="text-xl font-bold text-gray-900">Phase 1: Data Ingestion</h1>
                <p className="text-sm text-gray-600">Database connection and analysis dashboard</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                {getStatusIcon()}
                <span className={`text-sm font-medium ${getStatusColor()}`}>
                  {getStatusText()}
                </span>
              </div>
              
              <button
                onClick={handleRefresh}
                className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-colors duration-200"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        {/* Connection Status and Health */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-4">
          <div className="lg:col-span-2">
            <DatabaseConnection onConnectionUpdate={handleConnectionUpdate} />
          </div>
          <div>
            <ConnectionStatus 
              databaseInfo={databaseInfo} 
              lastRefresh={lastRefresh}
            />
          </div>
        </div>

        {/* Main Dashboard Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Field Statistics */}
          <div className="xl:col-span-2">
            <div className="bg-white rounded-lg shadow-sm border">
              <div className="px-6 py-4 border-b border-gray-200">
                <div className="flex items-center space-x-2">
                  <BarChart3 className="w-5 h-5 text-primary-600" />
                  <h2 className="text-lg font-semibold text-gray-900">Field Statistics</h2>
                </div>
                <p className="text-sm text-gray-600 mt-1">
                  Comprehensive analysis of field coverage and data quality
                </p>
              </div>
              <div className="p-6">
                <FieldStatistics 
                  databaseInfo={databaseInfo}
                  isAnalyzing={isAnalyzing}
                  onAnalysisStart={() => setIsAnalyzing(true)}
                  onAnalysisComplete={() => setIsAnalyzing(false)}
                />
              </div>
            </div>
          </div>

          {/* Statute Analysis */}
          <div>
            <div className="bg-white rounded-lg shadow-sm border">
              <div className="px-6 py-4 border-b border-gray-200">
                <div className="flex items-center space-x-2">
                  <FileText className="w-5 h-5 text-primary-600" />
                  <h2 className="text-lg font-semibold text-gray-900">Statute Analysis</h2>
                </div>
                <p className="text-sm text-gray-600 mt-1">
                  Unique statute names and distribution analysis
                </p>
              </div>
              <div className="p-6">
                <StatuteAnalysis 
                  databaseInfo={databaseInfo}
                  lastRefresh={lastRefresh}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Sample Data Viewer */}
        <div className="mt-8">
          <div className="bg-white rounded-lg shadow-sm border">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center space-x-2">
                <Activity className="w-5 h-5 text-primary-600" />
                <h2 className="text-lg font-semibold text-gray-900">Sample Data Viewer</h2>
              </div>
              <p className="text-sm text-gray-600 mt-1">
                Browse and analyze sample documents from the collection
              </p>
            </div>
            <div className="p-6">
              <SampleDataViewer 
                databaseInfo={databaseInfo}
                lastRefresh={lastRefresh}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Phase1;
