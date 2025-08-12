// Phase progress management utilities
export const PHASE_STATUS = {
  LOCKED: 'locked',
  READY: 'ready',
  IN_PROGRESS: 'in-progress',
  COMPLETED: 'completed'
};

export interface PhaseProgress {
  status: string;
  progress: number;
}

export interface PhaseProgressData {
  [phaseId: number]: PhaseProgress;
}

// Update phase progress in localStorage
export const updatePhaseProgress = (phaseId: number, status: string, progress: number): void => {
  try {
    const existingData = localStorage.getItem('phase_progress');
    const progressData: PhaseProgressData = existingData ? JSON.parse(existingData) : {};
    
    progressData[phaseId] = { status, progress };
    localStorage.setItem('phase_progress', JSON.stringify(progressData));
  } catch (error) {
    console.error('Error updating phase progress:', error);
  }
};

// Get phase progress from localStorage
export const getPhaseProgress = (phaseId: number): PhaseProgress | null => {
  try {
    const existingData = localStorage.getItem('phase_progress');
    if (!existingData) return null;
    
    const progressData: PhaseProgressData = JSON.parse(existingData);
    return progressData[phaseId] || null;
  } catch (error) {
    console.error('Error getting phase progress:', error);
    return null;
  }
};

// Get all phase progress data
export const getAllPhaseProgress = (): PhaseProgressData => {
  try {
    const existingData = localStorage.getItem('phase_progress');
    return existingData ? JSON.parse(existingData) : {};
  } catch (error) {
    console.error('Error getting all phase progress:', error);
    return {};
  }
};

// Mark phase as completed
export const completePhase = (phaseId: number): void => {
  updatePhaseProgress(phaseId, PHASE_STATUS.COMPLETED, 100);
};

// Mark phase as in progress
export const startPhase = (phaseId: number): void => {
  updatePhaseProgress(phaseId, PHASE_STATUS.IN_PROGRESS, 0);
};

// Update phase progress percentage
export const updatePhaseProgressPercentage = (phaseId: number, progress: number): void => {
  try {
    const existingData = localStorage.getItem('phase_progress');
    const progressData: PhaseProgressData = existingData ? JSON.parse(existingData) : {};
    
    if (progressData[phaseId]) {
      progressData[phaseId].progress = Math.min(100, Math.max(0, progress));
      localStorage.setItem('phase_progress', JSON.stringify(progressData));
    }
  } catch (error) {
    console.error('Error updating phase progress percentage:', error);
  }
};

// Reset all phase progress
export const resetAllPhaseProgress = (): void => {
  try {
    localStorage.removeItem('phase_progress');
  } catch (error) {
    console.error('Error resetting phase progress:', error);
  }
};

// Check if a phase is completed
export const isPhaseCompleted = (phaseId: number): boolean => {
  const progress = getPhaseProgress(phaseId);
  return progress?.status === PHASE_STATUS.COMPLETED;
};

// Check if a phase is ready to start
export const isPhaseReady = (phaseId: number): boolean => {
  const progress = getPhaseProgress(phaseId);
  return progress?.status === PHASE_STATUS.READY;
};

// Check if a phase is in progress
export const isPhaseInProgress = (phaseId: number): boolean => {
  const progress = getPhaseProgress(phaseId);
  return progress?.status === PHASE_STATUS.IN_PROGRESS;
};

// Check if a phase is locked
export const isPhaseLocked = (phaseId: number): boolean => {
  const progress = getPhaseProgress(phaseId);
  return progress?.status === PHASE_STATUS.LOCKED;
};
