import React from 'react';
import { Loader2, LucideIcon } from 'lucide-react';

interface ProcessingButtonProps {
  onClick: () => void;
  disabled?: boolean;
  isProcessing?: boolean;
  icon?: LucideIcon;
  children: React.ReactNode;
  progressText?: string;
  variant?: 'primary' | 'secondary' | 'success' | 'warning' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
  className?: string;
}

const ProcessingButton: React.FC<ProcessingButtonProps> = ({
  onClick,
  disabled = false,
  isProcessing = false,
  icon: Icon,
  children,
  progressText,
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  className = ''
}) => {
  const baseClasses = 'inline-flex items-center justify-center font-medium rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';
  
  const variantClasses = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
    secondary: 'bg-gray-600 text-white hover:bg-gray-700 focus:ring-gray-500',
    success: 'bg-green-600 text-white hover:bg-green-700 focus:ring-green-500',
    warning: 'bg-yellow-600 text-white hover:bg-yellow-700 focus:ring-yellow-500',
    danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500'
  };
  
  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base'
  };
  
  const widthClass = fullWidth ? 'w-full' : '';
  
  const combinedClasses = `${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${widthClass} ${className}`;

  return (
    <button
      onClick={onClick}
      disabled={disabled || isProcessing}
      className={combinedClasses}
    >
      {isProcessing ? (
        <>
          <Loader2 className={`animate-spin mr-2 ${size === 'sm' ? 'w-3 h-3' : size === 'lg' ? 'w-5 h-5' : 'w-4 h-4'}`} />
          {progressText || 'Processing...'}
        </>
      ) : (
        <>
          {Icon && <Icon className={`mr-2 ${size === 'sm' ? 'w-3 h-3' : size === 'lg' ? 'w-5 h-5' : 'w-4 h-4'}`} />}
          {children}
        </>
      )}
    </button>
  );
};

export default ProcessingButton;
