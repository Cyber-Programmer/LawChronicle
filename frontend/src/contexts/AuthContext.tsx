import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authService } from '../services/authService';

interface User {
  user_id: string;
  username: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const checkAuth = async () => {
    console.log('🔍 AuthContext: Starting checkAuth...');
    
    try {
      const storedToken = localStorage.getItem('token');
      console.log('🔍 AuthContext: Stored token:', storedToken ? 'exists' : 'none');
      
      if (!storedToken) {
        console.log('🔍 AuthContext: No token, setting unauthenticated');
        setIsAuthenticated(false);
        setUser(null);
        setToken(null);
        setIsLoading(false);
        return;
      }

      console.log('🔍 AuthContext: Validating token...');
      const response = await authService.getCurrentUser();
      const userData = response.data;
      
      console.log('🔍 AuthContext: Token valid, user data:', userData);
      setIsAuthenticated(true);
      setUser(userData);
      setToken(storedToken);
    } catch (error) {
      console.error('🔍 AuthContext: Token validation failed:', error);
      // Token is invalid, remove it
      localStorage.removeItem('token');
      setIsAuthenticated(false);
      setUser(null);
      setToken(null);
    } finally {
      console.log('🔍 AuthContext: Setting isLoading to false');
      setIsLoading(false);
    }
  };

  const login = async (username: string, password: string) => {
    console.log('🔍 AuthContext: Login attempt for user:', username);
    
    try {
      setIsLoading(true);
      
      const response = await authService.login(username, password);
      const { access_token } = response.data;
      
      console.log('🔍 AuthContext: Login successful, token received');
      
      // Store token immediately
      localStorage.setItem('token', access_token);
      setToken(access_token);
      
      // Get user info
      const userResponse = await authService.getCurrentUser();
      const userData = userResponse.data;
      
      console.log('🔍 AuthContext: User info retrieved:', userData);
      
      // Update state immediately - this will trigger UI re-render
      setIsAuthenticated(true);
      setUser(userData);
      
      return { success: true };
    } catch (error) {
      console.error('🔍 AuthContext: Login failed:', error);
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Login failed' 
      };
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    console.log('🔍 AuthContext: Logout initiated');
    
    try {
      // Call logout API if needed
      await authService.logout();
    } catch (error) {
      // Continue with logout even if API call fails
      console.warn('Logout API call failed:', error);
    } finally {
      // Clear local state and storage immediately - this will trigger UI re-render
      localStorage.removeItem('token');
      setIsAuthenticated(false);
      setUser(null);
      setToken(null);
      console.log('🔍 AuthContext: Logout completed, state cleared');
    }
  };

  // Initialize authentication state on mount
  useEffect(() => {
    console.log('🔍 AuthContext: useEffect triggered, calling checkAuth');
    checkAuth().catch(error => {
      console.error('🔍 AuthContext: checkAuth failed in useEffect:', error);
      setIsLoading(false);
    });
  }, []);

  const value: AuthContextType = {
    isAuthenticated,
    user,
    token,
    isLoading,
    login,
    logout,
    checkAuth,
  };

  console.log('🔍 AuthContext: Rendering with state:', { isAuthenticated, isLoading, user: user?.username });

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
