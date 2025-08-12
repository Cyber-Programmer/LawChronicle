import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Phase1 from './pages/Phase1';
import Phase2 from './pages/Phase2';
import Phase3 from './pages/Phase3';

// Fallback component that always renders
function FallbackComponent() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">LawChronicle</h1>
        <p className="text-gray-600">Loading application...</p>
        <div className="mt-4 animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
      </div>
    </div>
  );
}

function AppRoutes() {
  console.log('🔍 AppRoutes: Component rendering');
  
  // Hooks must be called at the top level, not inside try-catch
  const { isAuthenticated, isLoading } = useAuth();
  
  console.log('🔍 AppRoutes: Auth state:', { isAuthenticated, isLoading });

  if (isLoading) {
    console.log('🔍 AppRoutes: Showing loading spinner');
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">LawChronicle</h1>
          <p className="text-gray-600">Initializing...</p>
          <div className="mt-4 animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600 mx-auto"></div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    console.log('🔍 AppRoutes: Showing login page');
    return <Login />;
  }

  console.log('🔍 AppRoutes: Showing authenticated layout');
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/phase1" element={<Phase1 />} />
        <Route path="/phase2" element={<Phase2 />} />
        <Route path="/phase3" element={<Phase3 />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Layout>
  );
}

function App() {
  console.log('🔍 App: Component rendering');
  
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

export default App;
