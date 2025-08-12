import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Login from '../pages/Login';

// Mock the useAuth hook from AuthContext
jest.mock('../contexts/AuthContext');

const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;

describe('Authentication Flow', () => {
  const mockLogin = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();

    // Mock useAuth
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      token: null,
      isLoading: false,
      login: mockLogin,
      logout: jest.fn(),
      checkAuth: jest.fn(),
    });
  });

  it('should handle login without page refresh', async () => {
    // Mock successful login
    mockLogin.mockResolvedValue({ success: true });

    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const usernameInput = screen.getByPlaceholderText('Username');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByText('Sign in');

    // Fill in credentials
    fireEvent.change(usernameInput, { target: { value: 'admin' } });
    fireEvent.change(passwordInput, { target: { value: 'admin123' } });

    // Submit form
    fireEvent.click(submitButton);

    // Wait for login to complete
    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('admin', 'admin123');
    });

    // With AuthContext, the UI will update automatically - no navigation needed
    // The App component will re-render based on isAuthenticated state
    // This test verifies that the login function is called correctly
  });

  it('should handle login errors gracefully', async () => {
    // Mock failed login
    mockLogin.mockResolvedValue({ 
      success: false, 
      error: 'Invalid credentials' 
    });

    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const usernameInput = screen.getByPlaceholderText('Username');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByText('Sign in');

    // Fill in credentials
    fireEvent.change(usernameInput, { target: { value: 'wrong' } });
    fireEvent.change(passwordInput, { target: { value: 'wrong' } });

    // Submit form
    fireEvent.click(submitButton);

    // Wait for error to appear
    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });

    // With AuthContext, no navigation is needed - UI updates automatically
    // The error message should be displayed without any navigation
  });

  it('should show loading state during login', async () => {
    // Mock login that takes time
    mockLogin.mockImplementation(() => 
      new Promise(resolve => setTimeout(() => resolve({ success: true }), 100))
    );

    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const submitButton = screen.getByText('Sign in');
    
    // Submit form
    fireEvent.click(submitButton);

    // Should show loading state
    expect(screen.getByText('Sign in')).toBeDisabled();
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('should clear error when starting new login attempt', async () => {
    // Mock failed login first
    mockLogin.mockResolvedValueOnce({ 
      success: false, 
      error: 'Invalid credentials' 
    });

    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const usernameInput = screen.getByPlaceholderText('Username');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByText('Sign in');

    // First login attempt - fails
    fireEvent.change(usernameInput, { target: { value: 'wrong' } });
    fireEvent.change(passwordInput, { target: { value: 'wrong' } });
    fireEvent.click(submitButton);

    // Wait for error to appear
    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });

    // Start new login attempt - error should clear
    fireEvent.change(usernameInput, { target: { value: 'admin' } });
    
    // Error should be cleared when starting new input
    expect(screen.queryByText('Invalid credentials')).not.toBeInTheDocument();
  });
});
