import React from 'react';

interface BatchEditBarProps {
  selectedCount: number;
  batchNewName: string;
  onBatchNameChange: (name: string) => void;
  onBatchEdit: () => void;
}

const BatchEditBar: React.FC<BatchEditBarProps> = ({
  selectedCount,
  batchNewName,
  onBatchNameChange,
  onBatchEdit,
}) => (
  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
    <div className="flex items-center justify-between">
      <div className="text-blue-800">
        {selectedCount} statute group(s) selected
      </div>
      <div className="flex items-center space-x-2">
        <input
          type="text"
          placeholder="New statute name..."
          value={batchNewName}
          onChange={(e) => onBatchNameChange(e.target.value)}
          className="px-3 py-1 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={onBatchEdit}
          className="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700"
        >
          Update Selected
        </button>
      </div>
    </div>
  </div>
);

export default BatchEditBar;
