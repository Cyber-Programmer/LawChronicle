
import React from 'react';

interface Section {
  additional_fields?: Record<string, any>;
  number?: string;
  definition?: string;
  Statute?: string;
  content?: string;
}

interface StatuteGroup {
  _id: string;
  Statute_Name: string;
  Sections: Section[];
  section_count: number;
}

interface StatuteGroupListProps {
  statuteGroups: StatuteGroup[];
  selectedGroups: Set<string>;
  expandedGroups: Set<string>;
  expandedSections: Set<string>;
  editingId: string | null;
  editingName: string;
  onToggleSelection: (groupId: string) => void;
  onToggleGroupExpansion: (groupId: string) => void;
  onToggleSectionExpansion: (sectionId: string) => void;
  onStartEdit: (group: StatuteGroup) => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  onEditNameChange: (name: string) => void;
}

const StatuteGroupList: React.FC<StatuteGroupListProps> = ({
  statuteGroups,
  selectedGroups,
  expandedGroups,
  expandedSections,
  editingId,
  editingName,
  onToggleSelection,
  onToggleGroupExpansion,
  onToggleSectionExpansion,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onEditNameChange,
}) => {
  return (
    <div className="divide-y divide-gray-200">
      {statuteGroups.map((statute) => (
        <div key={statute._id} className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={selectedGroups.has(statute._id)}
                onChange={() => onToggleSelection(statute._id)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <button
                onClick={() => onToggleGroupExpansion(statute._id)}
                className="flex items-center space-x-2 text-left hover:text-blue-600"
              >
                {expandedGroups.has(statute._id) ? (
                  <span>▼</span>
                ) : (
                  <span>▶</span>
                )}
                <span className="font-medium text-gray-900">{statute.Statute_Name}</span>
                <span className="text-sm text-gray-500">({statute.section_count} sections)</span>
              </button>
            </div>
            <div className="flex items-center space-x-2">
              {editingId === statute._id ? (
                <>
                  <input
                    type="text"
                    value={editingName}
                    onChange={(e) => onEditNameChange(e.target.value)}
                    className="px-2 py-1 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
                  />
                  <button onClick={onSaveEdit} className="text-green-600 hover:text-green-800">💾</button>
                  <button onClick={onCancelEdit} className="text-gray-600 hover:text-gray-800">✖</button>
                </>
              ) : (
                <button
                  onClick={() => onStartEdit(statute)}
                  className="text-blue-600 hover:text-blue-800"
                  title="Edit statute name"
                >✏️</button>
              )}
            </div>
          </div>
          {expandedGroups.has(statute._id) && (
            <div className="mt-3 ml-8 space-y-2">
              <div className="text-sm text-gray-600 font-medium">Sections:</div>
              {statute.Sections && statute.Sections.length > 0 ? (
                <div className="space-y-2">
                  {statute.Sections.map((section: Section, index: number) => {
                    const sectionId = `${statute._id}-section-${index}`;
                    const isExpanded = expandedSections.has(sectionId);
                    const sectionNumber = section.additional_fields?.Section || section.number || `${index + 1}`;
                    const sectionDefinition = section.additional_fields?.Definition || section.definition || 'No title';
                    const sectionContent = section.Statute || section.content || 'No content available';
                    return (
                      <div key={index} className="border border-gray-200 rounded-lg">
                        <div className="bg-gray-50 p-3 flex items-center justify-between">
                          <button
                            onClick={() => onToggleSectionExpansion(sectionId)}
                            className="flex items-center space-x-2 text-left hover:text-blue-600 flex-1"
                          >
                            {isExpanded ? <span>▼</span> : <span>▶</span>}
                            <span className="font-medium text-gray-700">
                              {sectionNumber} : {sectionDefinition}
                            </span>
                          </button>
                          <div className="text-xs text-gray-500">{sectionContent.length} chars</div>
                        </div>
                        {isExpanded && (
                          <div className="p-4 border-t border-gray-200 bg-white">
                            <div className="space-y-3">
                              <div className="bg-blue-50 p-3 rounded-lg">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                  <div>
                                    <h4 className="text-sm font-semibold text-blue-800 mb-1">Section Number:</h4>
                                    <p className="text-sm text-blue-700 font-mono">{sectionNumber}</p>
                                  </div>
                                  <div>
                                    <h4 className="text-sm font-semibold text-blue-800 mb-1">Section Title:</h4>
                                    <p className="text-sm text-blue-700">{sectionDefinition}</p>
                                  </div>
                                </div>
                              </div>
                              <div>
                                <h4 className="text-sm font-semibold text-gray-800 mb-2">Full Statute Text:</h4>
                                <div className="text-sm text-gray-700 bg-gray-50 p-4 rounded-lg max-h-96 overflow-y-auto border">
                                  <pre className="whitespace-pre-wrap font-sans leading-relaxed">{sectionContent}</pre>
                                </div>
                              </div>
                              {section.additional_fields && Object.keys(section.additional_fields).length > 2 && (
                                <div>
                                  <h4 className="text-sm font-semibold text-gray-800 mb-2">Additional Information:</h4>
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                    {Object.entries(section.additional_fields).map(([key, value]) => {
                                      if (["Section", "Definition"].includes(key)) return null;
                                      if (!value || (typeof value === "string" && value.trim() === "")) return null;
                                      return (
                                        <div key={key} className="bg-yellow-50 p-2 rounded">
                                          <h5 className="text-xs font-semibold text-yellow-800 mb-1 capitalize">{key.replace(/_/g, ' ')}:</h5>
                                          <p className="text-xs text-yellow-700">{typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}</p>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-gray-500 text-sm">No sections found</div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default StatuteGroupList;
