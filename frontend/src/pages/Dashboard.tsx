import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Database, 
  FileText, 
  Scissors, 
  Calendar, 
  GitBranch, 
  Layers,
  Play,
  CheckCircle,
  Clock,
  Loader2,
  Pause,
  BarChart3,
  Eye
} from 'lucide-react';
import { 
  PHASE_STATUS, 
  updatePhaseProgress, 
  getAllPhaseProgress
} from '../utils/phaseProgress';

// Phase configuration with dependencies and status
interface Phase {
  id: number;
  name: string;
  description: string;
  icon: any;
  status: string;
  progress: number;
  color: string;
  dependencies: number[]; // IDs of phases that must be completed first
  route: string;
}

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  
  // Phase state management
  const [phases, setPhases] = useState<Phase[]>([
    {
      id: 1,
      name: 'Data Ingestion & Analysis',
      description: 'Connect to existing MongoDB, analyze raw data structure, show field statistics',
      icon: Database,
      status: PHASE_STATUS.READY,
      progress: 0,
      color: 'blue',
      dependencies: [], // No dependencies - can run independently
      route: '/phase1'
    },
    {
      id: 2,
      name: 'Database Normalization',
      description: 'Create clean database structure, normalize statute names, sort alphabetically',
      icon: FileText,
      status: PHASE_STATUS.READY,
      progress: 0,
      color: 'green',
      dependencies: [], // No dependencies - can run independently
      route: '/phase2'
    },
    {
      id: 3,
      name: 'Field Cleaning & Splitting',
      description: 'Clean fields, remove duplicates, organize sections, bring common fields up',
      icon: Scissors,
      status: PHASE_STATUS.READY,
      progress: 0,
      color: 'purple',
      dependencies: [], // No dependencies - can run independently
      route: '/phase3'
    },
    {
      id: 4,
      name: 'Date Processing',
      description: 'Extract, parse, and standardize dates using AI and regex',
      icon: Calendar,
      status: PHASE_STATUS.READY,
      progress: 0,
      color: 'orange',
      dependencies: [], // No dependencies - can run independently
      route: '/phase4'
    },
    {
      id: 5,
      name: 'Statute Versioning',
      description: 'Group statutes by base names, assign versions, remove duplicates',
      icon: GitBranch,
      status: PHASE_STATUS.READY, // Changed from LOCKED to READY
      progress: 0,
      color: 'indigo',
      dependencies: [], // No dependencies - can run independently
      route: '/phase5'
    },
    {
      id: 6,
      name: 'Section Versioning',
      description: 'Split sections, assign versions, create final schema',
      icon: Layers,
      status: PHASE_STATUS.LOCKED,
      progress: 0,
      color: 'pink',
      dependencies: [5], // Requires Phase 5 to be completed
      route: '/phase6'
    }
  ]);

  const [isLoading, setIsLoading] = useState(false);

  // Load phase progress from localStorage on mount
  useEffect(() => {
    const progressData = getAllPhaseProgress();
    if (Object.keys(progressData).length > 0) {
      setPhases(prevPhases => 
        prevPhases.map(phase => ({
          ...phase,
          ...progressData[phase.id]
        }))
      );
    }

    // Phase 4 is now accessible without dependencies
  }, []);

  // Listen for storage changes to sync phase progress across tabs
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'phase_progress' && e.newValue) {
        try {
          const progressData = JSON.parse(e.newValue);
          setPhases(prevPhases => 
            prevPhases.map(phase => ({
              ...phase,
              ...progressData[phase.id]
            }))
          );
        } catch (error) {
          console.error('Error parsing storage change:', error);
        }
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  // Save phase progress to localStorage when it changes
  useEffect(() => {
    const progressData = phases.reduce((acc, phase) => {
      acc[phase.id] = { status: phase.status, progress: phase.progress };
      return acc;
    }, {} as Record<number, { status: string; progress: number }>);
    
    localStorage.setItem('phase_progress', JSON.stringify(progressData));
  }, [phases]);

  // Since all phases are now independent, no dependency checking needed
  // All phases can be accessed and run independently

  // Update phase status and progress
  const updatePhaseStatus = (phaseId: number, status: string, progress: number) => {
    updatePhaseProgress(phaseId, status, progress);
    setPhases(prevPhases => 
      prevPhases.map(phase => 
        phase.id === phaseId 
          ? { ...phase, status, progress }
          : phase
      )
    );
  };

  // Start a specific phase
  const startPhase = async (phase: Phase) => {
    if (phase.status !== PHASE_STATUS.READY) return;
    
    setIsLoading(true);
    updatePhaseStatus(phase.id, PHASE_STATUS.IN_PROGRESS, 0);
    
    // Simulate phase execution (replace with actual API calls)
    try {
      // Navigate to the phase
      navigate(phase.route);
    } catch (error) {
      console.error(`Error starting Phase ${phase.id}:`, error);
      updatePhaseStatus(phase.id, PHASE_STATUS.READY, 0);
    } finally {
      setIsLoading(false);
    }
  };

  // Start all available phases
  const startAllPhases = async () => {
    const readyPhases = phases.filter(phase => phase.status === PHASE_STATUS.READY);
    if (readyPhases.length === 0) return;
    
    setIsLoading(true);
    try {
      // Start the first available phase
      const firstPhase = readyPhases[0];
      await startPhase(firstPhase);
    } catch (error) {
      console.error('Error starting all phases:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Pause all running phases
  const pauseAllPhases = async () => {
    const runningPhases = phases.filter(phase => phase.status === PHASE_STATUS.IN_PROGRESS);
    if (runningPhases.length === 0) return;
    
    setIsLoading(true);
    try {
      // Pause all running phases
      runningPhases.forEach(phase => {
        updatePhaseStatus(phase.id, PHASE_STATUS.READY, phase.progress);
      });
    } catch (error) {
      console.error('Error pausing phases:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Refresh phase status from localStorage
  const refreshPhaseStatus = () => {
    const progressData = getAllPhaseProgress();
    setPhases(prevPhases => 
      prevPhases.map(phase => ({
        ...phase,
        ...progressData[phase.id]
      }))
    );
  };

  // Simulate phase completion for testing (remove in production)
  const simulatePhaseCompletion = (phaseId: number) => {
    updatePhaseStatus(phaseId, PHASE_STATUS.COMPLETED, 100);
  };

  // Get status icon based on phase status
  const getStatusIcon = (status: string) => {
    switch (status) {
      case PHASE_STATUS.COMPLETED:
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case PHASE_STATUS.IN_PROGRESS:
        return <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />;
      case PHASE_STATUS.READY:
        return null; // No icon for ready phases
      case PHASE_STATUS.LOCKED:
        return <Clock className="h-5 w-5 text-gray-400" />;
      default:
        return <Clock className="h-5 w-5 text-gray-400" />;
    }
  };

  // Get status color and text
  const getStatusInfo = (status: string) => {
    switch (status) {
      case PHASE_STATUS.COMPLETED:
        return { color: 'bg-green-100 text-green-800', text: 'Completed' };
      case PHASE_STATUS.IN_PROGRESS:
        return { color: 'bg-blue-100 text-blue-800', text: 'In Progress' };
      case PHASE_STATUS.READY:
        return { color: 'bg-gray-100 text-gray-800', text: 'Ready' };
      case PHASE_STATUS.LOCKED:
        return { color: 'bg-gray-100 text-gray-600', text: 'Locked' };
      default:
        return { color: 'bg-gray-100 text-gray-800', text: 'Unknown' };
    }
  };

  // Get progress bar color
  const getProgressColor = (status: string, progress: number) => {
    if (status === PHASE_STATUS.COMPLETED) return 'bg-green-600';
    if (status === PHASE_STATUS.IN_PROGRESS) return 'bg-blue-600';
    if (status === PHASE_STATUS.READY) return 'bg-gray-400';
    return 'bg-gray-300';
  };

  // Calculate button states
  const isStartAllEnabled = phases.some(phase => phase.status === PHASE_STATUS.READY);
  const isPauseAllEnabled = phases.some(phase => phase.status === PHASE_STATUS.IN_PROGRESS);
  const isViewDatabaseEnabled = phases.slice(0, 2).some(phase => phase.status === PHASE_STATUS.COMPLETED);
  const isViewReportsEnabled = phases.slice(2).some(phase => phase.status === PHASE_STATUS.COMPLETED);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              LawChronicle Processing Hub
            </h1>
            <p className="text-gray-600 text-lg">
              Your complete legal document transformation toolkit - Process and organize legal documents efficiently
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={refreshPhaseStatus}
              className="inline-flex items-center px-3 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition-colors duration-200"
            >
              <Database className="h-4 w-4 mr-2" />
              Refresh Status
            </button>
            {/* Testing controls - remove in production */}
            <div className="flex items-center space-x-1">
              <button
                onClick={() => simulatePhaseCompletion(1)}
                className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
              >
                Complete P1
              </button>
              <button
                onClick={() => simulatePhaseCompletion(2)}
                className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200"
              >
                Complete P2
              </button>
              <button
                onClick={() => simulatePhaseCompletion(3)}
                className="px-2 py-1 text-xs bg-purple-100 text-purple-700 rounded hover:bg-purple-200"
              >
                Complete P3
              </button>
              <button
                onClick={() => simulatePhaseCompletion(4)}
                className="px-2 py-1 text-xs bg-orange-100 text-orange-700 rounded hover:bg-orange-200"
              >
                Complete P4
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Pipeline Summary */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Pipeline Summary</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">
              {phases.filter(p => p.status === PHASE_STATUS.READY).length}
            </div>
            <div className="text-sm text-gray-600">Ready to Start</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">
              {phases.filter(p => p.status === PHASE_STATUS.IN_PROGRESS).length}
            </div>
            <div className="text-sm text-gray-600">In Progress</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">
              {phases.filter(p => p.status === PHASE_STATUS.COMPLETED).length}
            </div>
            <div className="text-sm text-gray-600">Completed</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-600">
              {phases.filter(p => p.status === PHASE_STATUS.LOCKED).length}
            </div>
            <div className="text-sm text-gray-600">Locked</div>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-600">Overall Progress:</span>
            <span className="font-medium">
              {Math.round(
                (phases.filter(p => p.status === PHASE_STATUS.COMPLETED).length / phases.length) * 100
              )}%
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
            <div
              className="bg-green-600 h-2 rounded-full transition-all duration-500 ease-out"
              style={{ 
                width: `${(phases.filter(p => p.status === PHASE_STATUS.COMPLETED).length / phases.length) * 100}%` 
              }}
            ></div>
          </div>
        </div>
      </div>

      {/* Pipeline Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {phases.map((phase) => {
          const statusInfo = getStatusInfo(phase.status);
          const progressColor = getProgressColor(phase.status, phase.progress);
          
          return (
            <div
              key={phase.id}
              className={`bg-white rounded-lg shadow-sm border transition-all duration-200 ${
                phase.status === PHASE_STATUS.IN_PROGRESS 
                  ? 'border-blue-300 shadow-md' 
                  : phase.status === PHASE_STATUS.COMPLETED 
                    ? 'border-green-300 shadow-md'
                    : 'border-gray-200 hover:shadow-md'
              }`}
            >
              <div className="p-4">
                <div className="flex items-start justify-between mb-3">
                  <div className={`p-2 rounded-lg bg-${phase.color}-100`}>
                    <phase.icon className={`h-6 w-6 text-${phase.color}-600`} />
                  </div>
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(phase.status)}
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusInfo.color}`}>
                      {statusInfo.text}
                    </span>
                  </div>
                </div>

                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  Phase {phase.id}: {phase.name}
                </h3>
                
                <p className="text-gray-600 text-sm mb-3">
                  {phase.description}
                </p>

                {/* Dependencies indicator */}
                {phase.dependencies.length > 0 && (
                  <div className="mb-3">
                    <div className="text-xs text-gray-500 mb-1">
                      Requires: {phase.dependencies.map(depId => `Phase ${depId}`).join(', ')}
                    </div>
                    <div className="flex space-x-1">
                      {phase.dependencies.map(depId => {
                        const depPhase = phases.find(p => p.id === depId);
                        const isCompleted = depPhase?.status === PHASE_STATUS.COMPLETED;
                        return (
                          <div
                            key={depId}
                            className={`w-2 h-2 rounded-full ${
                              isCompleted ? 'bg-green-500' : 'bg-gray-300'
                            }`}
                            title={`Phase ${depId}: ${isCompleted ? 'Completed' : 'Not Completed'}`}
                          />
                        );
                      })}
                    </div>
                  </div>
                )}

                                 {/* Progress bar - only show for in-progress or completed phases */}
                 {(phase.status === PHASE_STATUS.IN_PROGRESS || phase.status === PHASE_STATUS.COMPLETED) && (
                   <div className="mb-3">
                     <div className="flex items-center justify-between text-sm text-gray-600 mb-1">
                       <span>Progress</span>
                       <span className="font-medium">{phase.progress}%</span>
                     </div>
                     <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                       <div
                         className={`${progressColor} h-2 rounded-full transition-all duration-500 ease-out ${
                           phase.status === PHASE_STATUS.IN_PROGRESS ? 'animate-pulse' : ''
                         }`}
                         style={{ width: `${phase.progress}%` }}
                         role="progressbar"
                         aria-valuenow={phase.progress}
                         aria-valuemin={0}
                         aria-valuemax={100}
                         aria-label={`Phase ${phase.id} progress: ${phase.progress}%`}
                       ></div>
                     </div>
                   </div>
                 )}

                                 {/* Action button */}
                 {phase.status === PHASE_STATUS.READY ? (
                   <button
                     onClick={() => startPhase(phase)}
                     disabled={isLoading}
                     className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                     title={`Start Phase ${phase.id}: ${phase.name}`}
                     aria-label={`Start Phase ${phase.id}: ${phase.name}`}
                   >
                     {isLoading ? (
                       <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                     ) : (
                       <Play className="h-4 w-4 mr-2" />
                     )}
                     Start Phase {phase.id}
                   </button>
                 ) : phase.status === PHASE_STATUS.IN_PROGRESS ? (
                   <button
                     onClick={() => updatePhaseStatus(phase.id, PHASE_STATUS.READY, phase.progress)}
                     className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition-colors duration-200"
                     title={`Pause Phase ${phase.id}: ${phase.name}`}
                     aria-label={`Pause Phase ${phase.id}: ${phase.name}`}
                   >
                     <Pause className="h-4 w-4 mr-2" />
                     Pause Phase {phase.id}
                   </button>
                 ) : phase.status === PHASE_STATUS.COMPLETED ? (
                   <button
                     onClick={() => navigate(phase.route)}
                     className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition-colors duration-200"
                     title={`View Phase ${phase.id}: ${phase.name}`}
                     aria-label={`View Phase ${phase.id}: ${phase.name}`}
                   >
                     <Eye className="h-4 w-4 mr-2" />
                     View Phase {phase.id}
                   </button>
                 ) : (
                   <div 
                     className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-500 bg-gray-100 cursor-not-allowed"
                     title={`Phase ${phase.id} is locked. Complete required dependencies first.`}
                     role="status"
                     aria-label={`Phase ${phase.id} is locked. Complete required dependencies first.`}
                   >
                     Phase Not Available
                   </div>
                 )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <button 
            onClick={startAllPhases}
            disabled={!isStartAllEnabled || isLoading}
            className="flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Play className="h-4 w-4 mr-2" />
            )}
            Start All Phases
          </button>
          
          <button 
            onClick={pauseAllPhases}
            disabled={!isPauseAllEnabled || isLoading}
            className="flex items-center justify-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Pause className="h-4 w-4 mr-2" />
            Pause All
          </button>
          
          <button 
            onClick={() => navigate('/phase1')}
            disabled={!isViewDatabaseEnabled}
            className="flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Database className="h-4 w-4 mr-2" />
            View Database
          </button>
          
          <button 
            onClick={() => navigate('/phase3')}
            disabled={!isViewReportsEnabled}
            className="flex items-center justify-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <BarChart3 className="h-4 w-4 mr-2" />
            View Reports
          </button>
        </div>
      </div>

      {/* System Status */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">System Status</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center p-4 bg-green-50 rounded-lg border border-green-200">
            <div className="text-2xl font-bold text-green-600">Online</div>
            <div className="text-sm text-green-600">Backend API</div>
          </div>
          <div className="text-center p-4 bg-green-50 rounded-lg border border-green-200">
            <div className="text-2xl font-bold text-green-600">Connected</div>
            <div className="text-sm text-green-600">MongoDB</div>
          </div>
          <div className="text-center p-4 bg-green-50 rounded-lg border border-green-200">
            <div className="text-2xl font-bold text-green-600">Ready</div>
            <div className="text-sm text-green-600">AI Services</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
