import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { 
  Database, 
  Menu,
  X,
  LogOut,
  User,
  FileText,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Scissors
} from 'lucide-react';

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false); // Mobile sidebar
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false); // Desktop sidebar collapse
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const { user, logout } = useAuth();
  const location = useLocation();
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setUserDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const navigation = [
    {
      name: 'Dashboard',
      href: '/dashboard',
      icon: Database,
      description: 'Overview and status'
    },
    {
      name: 'Phase 1',
      href: '/phase1',
      icon: FileText,
      description: 'Data ingestion and analysis'
    },
    {
      name: 'Phase 2',
      href: '/phase2',
      icon: FileText,
      description: 'Database normalization'
    },
    {
      name: 'Phase 3',
      href: '/phase3',
      icon: Scissors,
      description: 'Field cleaning and splitting'
    }
  ];

  const handleLogout = async () => {
    if (isLoggingOut) return; // Prevent multiple logout attempts
    
    setIsLoggingOut(true);
    try {
      await logout();
      // No need to navigate manually - AuthContext will handle UI update
    } catch (error) {
      console.error('Logout error:', error);
      // AuthContext will still handle the state update
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-gray-600 bg-opacity-75 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Top bar - Fixed at top */}
      <div className="bg-white shadow-sm border-b border-gray-200 z-40 sticky top-0">
        <div className="flex items-center justify-between h-16 px-4 sm:px-6 lg:px-8">
          <div className="flex items-center">
            {/* Mobile menu button */}
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-md text-gray-400 hover:text-gray-600 mr-2"
            >
              <Menu className="h-5 w-5" />
            </button>
            
            {/* Desktop sidebar toggle */}
            <button
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="hidden lg:block p-2 rounded-md text-gray-400 hover:text-gray-600 mr-3 transition-colors hover:bg-gray-100 rounded-lg"
            >
              <Menu className="h-5 w-5" />
            </button>
            
            <h2 className="text-lg font-semibold text-gray-900">
              {navigation.find(item => item.href === location.pathname)?.name || 'Dashboard'}
            </h2>
          </div>

          {/* User dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setUserDropdownOpen(!userDropdownOpen)}
              className="flex items-center space-x-3 p-2 rounded-md text-gray-700 hover:bg-gray-100 transition-colors duration-200"
            >
              <div className="h-8 w-8 bg-primary-100 rounded-full flex items-center justify-center">
                <User className="h-4 w-4 text-primary-600" />
              </div>
              <div className="hidden sm:block text-left">
                <p className="text-sm font-medium text-gray-900">
                  {user?.username || 'Admin'}
                </p>
                <p className="text-xs text-gray-500">Administrator</p>
              </div>
              <ChevronDown className="h-4 w-4 text-gray-400" />
            </button>

            {/* Dropdown menu */}
            {userDropdownOpen && (
              <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg ring-1 ring-black ring-opacity-5 z-50">
                <div className="py-1">
                  <div className="px-4 py-2 border-b border-gray-100">
                    <p className="text-sm font-medium text-gray-900">
                      {user?.username || 'Admin'}
                    </p>
                    <p className="text-xs text-gray-500">Administrator</p>
                  </div>
                  <button
                    onClick={async () => {
                      setUserDropdownOpen(false);
                      await handleLogout();
                    }}
                    disabled={isLoggingOut}
                    className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <LogOut className="h-4 w-4 mr-2" />
                    {isLoggingOut ? 'Signing out...' : 'Sign out'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main container with sidebar and content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar - Fixed height, scrollable */}
        <div className={`fixed left-0 z-30 bg-white shadow-lg transform transition-all duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } ${sidebarCollapsed ? 'lg:w-16' : 'lg:w-64'} w-64`} style={{ top: '64px', height: 'calc(100vh - 64px)' }}>
          
          {/* Header */}
          <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200 bg-gradient-to-r from-primary-600 to-primary-700">
            <div className={`flex items-center ${sidebarCollapsed ? 'justify-center' : 'justify-start'}`}>
              <div className="h-8 w-8 bg-white rounded-lg flex items-center justify-center shadow-sm">
                <Database className="h-5 w-5 text-primary-600" />
              </div>
              {!sidebarCollapsed && (
                <h1 className="ml-3 text-xl font-bold text-white">LawChronicle</h1>
              )}
            </div>
            
            {/* Close button for mobile */}
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden p-2 rounded-md text-white hover:bg-white/20 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Navigation - Scrollable */}
          <div className="flex-1 overflow-y-auto">
            <nav className="mt-6 px-3 pb-6">
              <div className="space-y-2">
                {navigation.map((item) => {
                  const isActive = location.pathname === item.href;
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={`group relative flex items-center px-3 py-3 text-sm font-medium rounded-lg transition-all duration-200 ${
                        isActive
                          ? 'bg-primary-50 text-primary-700 shadow-sm border-l-4 border-primary-600'
                          : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                      } ${sidebarCollapsed ? 'justify-center' : 'justify-start'}`}
                      onClick={() => setSidebarOpen(false)}
                      title={sidebarCollapsed ? item.name : ''}
                    >
                      <item.icon
                        className={`h-5 w-5 ${
                          isActive ? 'text-primary-600' : 'text-gray-400 group-hover:text-gray-500'
                        } ${sidebarCollapsed ? '' : 'mr-3'}`}
                      />
                      {!sidebarCollapsed && (
                        <div className="flex-1">
                          <div className="font-medium">{item.name}</div>
                          <div className="text-xs text-gray-500 mt-0.5">{item.description}</div>
                        </div>
                      )}
                      
                      {/* Tooltip for collapsed state */}
                      {sidebarCollapsed && (
                        <div className="absolute left-full ml-2 px-3 py-2 bg-gray-900 text-white text-sm rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-50 whitespace-nowrap pointer-events-none">
                          <div className="font-medium">{item.name}</div>
                          <div className="text-xs text-gray-300">{item.description}</div>
                          <div className="absolute left-0 top-1/2 transform -translate-y-1/2 -translate-x-1 w-2 h-2 bg-gray-900 rotate-45"></div>
                        </div>
                      )}
                    </Link>
                  );
                })}
              </div>
            </nav>
          </div>
        </div>

        {/* Main content area - Scrollable */}
        <div className="flex-1 flex flex-col">
          <div className="flex-1 overflow-y-auto">
            <main className="p-4 sm:p-6 lg:p-8 min-h-full">
              {children}
            </main>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Layout;
