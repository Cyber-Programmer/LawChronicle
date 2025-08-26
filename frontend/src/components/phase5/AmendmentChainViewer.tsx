import React from 'react';
import { ChevronRight, Calendar, FileText, Shield, AlertCircle } from 'lucide-react';
import type { AmendmentChain, AmendmentMember, ConstitutionalAnalysis } from './types';

interface AmendmentChainViewerProps {
  chain?: AmendmentChain;
  amendments?: string[];
  constitutionalAnalysis?: ConstitutionalAnalysis;
  isExpanded?: boolean;
  showFullDetails?: boolean;
}

interface AmendmentChainListProps {
  chains?: AmendmentChain[];
  onChainSelect?: (chain: AmendmentChain) => void;
  selectedChainId?: string;
}

// Simple amendment list viewer (for backwards compatibility)
export const SimpleAmendmentViewer: React.FC<{ amendments?: string[] }> = ({ amendments }) => {
  if (!amendments || amendments.length === 0) {
    return <span className="text-gray-400 text-sm ml-2">No amendments</span>;
  }

  return (
    <div className="ml-4 mt-2">
      <div className="text-xs text-blue-600 font-medium mb-1">Amendments ({amendments.length})</div>
      <ul className="space-y-1">
        {amendments.map((amendment, index) => (
          <li key={index} className="text-sm text-blue-600 flex items-center">
            <ChevronRight className="w-3 h-3 mr-1 text-blue-400" />
            {amendment}
          </li>
        ))}
      </ul>
    </div>
  );
};

// Constitutional analysis badge
const ConstitutionalBadge: React.FC<{ analysis?: ConstitutionalAnalysis }> = ({ analysis }) => {
  if (!analysis || !analysis.is_constitutional) {
    return null;
  }

  const getAmendmentTypeColor = (type: string) => {
    switch (type) {
      case 'amendment': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'repeal': return 'bg-red-100 text-red-800 border-red-200';
      case 'addition': return 'bg-green-100 text-green-800 border-green-200';
      case 'order': return 'bg-purple-100 text-purple-800 border-purple-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="flex items-center gap-2 mt-2">
      <div className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium border ${getAmendmentTypeColor(analysis.amendment_type)}`}>
        <Shield className="w-3 h-3 mr-1" />
        Constitutional {analysis.amendment_type}
      </div>
      {analysis.confidence > 0 && (
        <div className="text-xs text-gray-500">
          Confidence: {analysis.confidence}%
        </div>
      )}
    </div>
  );
};

// Amendment member card
const AmendmentMemberCard: React.FC<{ 
  member: AmendmentMember; 
  isLatest: boolean;
  showDetails?: boolean;
}> = ({ member, isLatest, showDetails = false }) => {
  const getPositionColor = (position: number) => {
    if (position === 0) return 'bg-green-50 border-green-200 text-green-800';
    return 'bg-blue-50 border-blue-200 text-blue-800';
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return 'Unknown date';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className={`
      relative p-3 rounded-lg border transition-all duration-200
      ${getPositionColor(member.position)}
      ${isLatest ? 'ring-2 ring-blue-300 shadow-md' : 'hover:shadow-sm'}
    `}>
      {/* Position indicator */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center">
          <div className="w-6 h-6 rounded-full bg-white border-2 border-current flex items-center justify-center text-xs font-bold">
            {member.position + 1}
          </div>
          <span className="ml-2 text-xs font-semibold">
            {member.amendment_type}
          </span>
        </div>
        {isLatest && (
          <div className="text-xs font-medium bg-blue-600 text-white px-2 py-1 rounded">
            Latest
          </div>
        )}
      </div>

      {/* Statute name */}
      <h4 className="font-medium text-sm leading-tight mb-2">
        {member.statute_name}
      </h4>

      {/* Date */}
      <div className="flex items-center text-xs text-gray-600">
        <Calendar className="w-3 h-3 mr-1" />
        {formatDate(member.date)}
      </div>

      {showDetails && (
        <div className="mt-2 pt-2 border-t border-current/20">
          <div className="text-xs text-gray-600">
            ID: {member.statute_id.slice(-8)}
          </div>
        </div>
      )}
    </div>
  );
};

// Main amendment chain viewer
const AmendmentChainViewer: React.FC<AmendmentChainViewerProps> = ({ 
  chain, 
  amendments, 
  constitutionalAnalysis,
  isExpanded = false,
  showFullDetails = false
}) => {
  // Handle simple amendments list (backwards compatibility)
  if (!chain && amendments) {
    return <SimpleAmendmentViewer amendments={amendments} />;
  }

  // Handle no chain data
  if (!chain || !chain.members || chain.members.length === 0) {
    return (
      <div className="text-gray-400 text-sm ml-2 flex items-center">
        <AlertCircle className="w-3 h-3 mr-1" />
        No amendment chain
      </div>
    );
  }

  // Sort members by position
  const sortedMembers = [...chain.members].sort((a, b) => a.position - b.position);
  const latestMember = sortedMembers[sortedMembers.length - 1];

  return (
    <div className="mt-3 space-y-3">
      {/* Chain header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center">
          <FileText className="w-4 h-4 text-blue-600 mr-2" />
          <span className="text-sm font-medium text-gray-900">
            Amendment Chain: {chain.base_name}
          </span>
        </div>
        <div className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
          {chain.total_amendments} amendments
        </div>
      </div>

      {/* Constitutional analysis badge */}
      <ConstitutionalBadge analysis={constitutionalAnalysis} />

      {/* Amendment members */}
      <div className="space-y-2">
        {isExpanded ? (
          // Full chain view
          <div className="grid gap-2">
            {sortedMembers.map((member) => (
              <AmendmentMemberCard
                key={`${member.statute_id}-${member.position}`}
                member={member}
                isLatest={member.statute_id === latestMember.statute_id}
                showDetails={showFullDetails}
              />
            ))}
          </div>
        ) : (
          // Compact view - show original and latest
          <div className="grid gap-2">
            {/* Original */}
            <AmendmentMemberCard
              member={sortedMembers[0]}
              isLatest={false}
              showDetails={showFullDetails}
            />
            
            {/* Show gap indicator if there are amendments in between */}
            {sortedMembers.length > 2 && (
              <div className="text-center py-2">
                <div className="text-xs text-gray-400 bg-gray-50 inline-block px-3 py-1 rounded-full">
                  ... {sortedMembers.length - 2} intermediate amendment{sortedMembers.length - 2 !== 1 ? 's' : ''} ...
                </div>
              </div>
            )}
            
            {/* Latest (if different from original) */}
            {sortedMembers.length > 1 && (
              <AmendmentMemberCard
                member={latestMember}
                isLatest={true}
                showDetails={showFullDetails}
              />
            )}
          </div>
        )}
      </div>

      {/* Chain metadata */}
      {showFullDetails && (
        <div className="mt-3 p-2 bg-gray-50 rounded text-xs text-gray-600">
          <div>Chain ID: {chain.chain_id}</div>
          <div>Created: {new Date(chain.creation_date).toLocaleString()}</div>
        </div>
      )}
    </div>
  );
};

// Amendment chain list component
export const AmendmentChainList: React.FC<AmendmentChainListProps> = ({ 
  chains, 
  onChainSelect, 
  selectedChainId 
}) => {
  if (!chains || chains.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
        <p>No amendment chains detected</p>
        <p className="text-sm mt-1">Run amendment chain detection first</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="text-sm font-medium text-gray-700 mb-3">
        Found {chains.length} amendment chain{chains.length !== 1 ? 's' : ''}
      </div>
      
      {chains.map((chain) => (
        <div
          key={chain.chain_id}
          className={`
            p-4 rounded-lg border cursor-pointer transition-all duration-200
            ${selectedChainId === chain.chain_id 
              ? 'border-blue-300 bg-blue-50 shadow-md' 
              : 'border-gray-200 hover:border-gray-300 hover:shadow-sm'
            }
          `}
          onClick={() => onChainSelect?.(chain)}
        >
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-medium text-gray-900">{chain.base_name}</h3>
            <div className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
              {chain.total_amendments} amendments
            </div>
          </div>
          
          <div className="text-sm text-gray-600 mb-3">
            {chain.members.length} statutes in chain
          </div>
          
          <AmendmentChainViewer 
            chain={chain} 
            isExpanded={selectedChainId === chain.chain_id}
            showFullDetails={false}
          />
        </div>
      ))}
    </div>
  );
};

export default AmendmentChainViewer;
