import React from 'react';

interface MessageBarProps {
  type: 'success' | 'error';
  text: string;
}

const MessageBar: React.FC<MessageBarProps> = ({ type, text }) => (
  <div className={`p-4 rounded-lg flex items-center ${
    type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
  }`}>
    {type === 'success' ? (
      <span className="mr-2">✔️</span>
    ) : (
      <span className="mr-2">⚠️</span>
    )}
    {text}
  </div>
);

export default MessageBar;
