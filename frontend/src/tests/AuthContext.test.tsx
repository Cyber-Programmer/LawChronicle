import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider, useAuth } from '../contexts/AuthContext';
import { authService } from '../services/authService';

// Mock the authService
jest.mock('../services/authService');
const mockAuthService = authService as jest.Mocked<typeof authService>;

// Test component that uses the auth context
const TestComponent = () => {
  const { isAuthenticated, user, isLoading } = useAuth();
  
  if (isLoading) return <div>Loading...</div>;
  if (isAuthenticated) return <div>Authenticated as {user?.username}</div>;
  return <div>Not authenticated</div>;
};

describe('AuthContext', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  it('should provide initial loading state', () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('should show not authenticated when no token exists', async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Not authenticated')).toBeInTheDocument();
    });
  });

  it('should show authenticated when valid token exists', async () => {
    // Mock localStorage to have a token
    localStorage.setItem('token', 'valid-token');
    
    // Mock successful user fetch
    mockAuthService.getCurrentUser.mockResolvedValue({
      data: { user_id: '1', username: 'admin' }
    });

    render(
      <BrowserRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Authenticated as admin')).toBeInTheDocument();
    });
  });

  it('should clear state when token is invalid', async () => {
    // Mock localStorage to have a token
    localStorage.setItem('token', 'invalid-token');
    
    // Mock failed user fetch
    mockAuthService.getCurrentUser.mockRejectedValue(new Error('Invalid token'));

    render(
      <BrowserRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Not authenticated')).toBeInTheDocument();
    });

    // Verify token was removed from localStorage
    expect(localStorage.getItem('token')).toBeNull();
  });
});
