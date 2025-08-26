import React from 'react';
import { X, Plus } from 'lucide-react';

export interface FieldMapping {
  source: string;
  target: string;
  enabled: boolean;
}

interface FieldMappingEditorProps {
  fieldMappings: FieldMapping[];
  updateFieldMapping: (index: number, field: keyof FieldMapping, value: any) => void;
  addFieldMapping: () => void;
  removeFieldMapping: (index: number) => void;
}

const FieldMappingEditor: React.FC<FieldMappingEditorProps> = ({
  fieldMappings,
  updateFieldMapping,
  addFieldMapping,
  removeFieldMapping
}) => (
  <div className="bg-white rounded-lg shadow p-6">
    <h3 className="text-lg font-semibold text-gray-900 mb-4">Field Mappings</h3>
    <p className="text-gray-600 mb-4">
      Define how section fields should be mapped and cleaned. Each mapping transforms a source field to a target field.
    </p>
    <div className="space-y-3">
      {fieldMappings.map((mapping, index) => (
        <div key={index} className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
          <input
            type="checkbox"
            checked={mapping.enabled}
            onChange={e => updateFieldMapping(index, 'enabled', e.target.checked)}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <div className="flex-1 grid grid-cols-2 gap-3">
            <input
              type="text"
              placeholder="Source field"
              value={mapping.source}
              onChange={e => updateFieldMapping(index, 'source', e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
            />
            <input
              type="text"
              placeholder="Target field"
              value={mapping.target}
              onChange={e => updateFieldMapping(index, 'target', e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            onClick={() => removeFieldMapping(index)}
            className="text-red-600 hover:text-red-800 p-1"
            title="Remove mapping"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
    <button
      onClick={addFieldMapping}
      className="mt-3 bg-blue-100 text-blue-700 px-4 py-2 rounded-lg hover:bg-blue-200 flex items-center"
    >
      <Plus className="w-4 h-4 mr-2" />
      Add Field Mapping
    </button>
  </div>
);

export default FieldMappingEditor;
