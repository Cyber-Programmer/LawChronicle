import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  ChevronDown, 
  ChevronRight, 
  Calendar, 
  MapPin, 
  FileText, 
  Tag, 
  Download, 
  Search,
  BarChart3,
  Shield,
  RefreshCw,
  AlertCircle,
  CheckCircle2
} from 'lucide-react';
import AmendmentChainViewer, { AmendmentChainList } from './AmendmentChainViewer';
import { Phase5ApiService } from './apiService';
import type { 
  StatuteGroup, 
  GroupedStatute, 
  GroupsResponse, 
  GroupingFilters,
  SortOptions,
  AmendmentChain,
  GroupingStatistics
} from './types';

interface GroupedStatutesViewerProps {
  refreshTrigger?: number;
  selectedCollection?: string;
  onRefresh?: () => void;
}

// Safe group filtering and sorting with enhanced intelligent features
const filterAndSortGroups = (
  groups: StatuteGroup[], 
  filters: GroupingFilters, 
  sortOptions: SortOptions
): StatuteGroup[] => {
  if (!groups || groups.length === 0) return [];

  let filtered = groups.filter(group => {
    if (!group) return false;

    // Search term filter - enhanced to include constitutional analysis
    if (filters.searchTerm) {
      const searchLower = filters.searchTerm.toLowerCase();
      const matchesTitle = (group.title || group.base_name || '').toLowerCase().includes(searchLower);
      const matchesProvince = group.provinces?.some(p => p.toLowerCase().includes(searchLower)) || 
                             group.province?.toLowerCase().includes(searchLower) || false;
      const matchesType = group.statute_type?.toLowerCase().includes(searchLower) || false;
      const matchesConstitutional = group.constitutional_info?.constitutional_base?.toLowerCase().includes(searchLower) || false;
      
      if (!matchesTitle && !matchesProvince && !matchesType && !matchesConstitutional) return false;
    }

    // Province filter
    if (filters.selectedProvince && filters.selectedProvince !== 'all') {
      const hasProvince = group.provinces?.includes(filters.selectedProvince) || 
                         group.province === filters.selectedProvince || false;
      if (!hasProvince) return false;
    }

    // Year filter
    if (filters.selectedYear && filters.selectedYear !== 'all') {
      const hasYear = group.years?.includes(filters.selectedYear) || false;
      if (!hasYear) return false;
    }

    // Constitutional filter
    if (filters.constitutionalOnly) {
      const isConstitutional = group.constitutional_info?.is_constitutional || false;
      if (!isConstitutional) return false;
    }

    // Amendment chain filter
    if (filters.showChainOnly) {
      const hasChain = group.amendment_chain && group.amendment_chain.members && 
                      group.amendment_chain.members.length > 1;
      if (!hasChain) return false;
    }

    // Amendment type filter
    if (filters.amendmentTypeFilter && filters.amendmentTypeFilter !== 'all') {
      const amendmentType = group.constitutional_info?.amendment_type;
      if (amendmentType !== filters.amendmentTypeFilter) return false;
    }

    return true;
  });

  // Enhanced sorting with intelligent analysis
  filtered.sort((a, b) => {
    let aValue: any, bValue: any;

    switch (sortOptions.field) {
      case 'name':
        aValue = a.title || a.base_name || '';
        bValue = b.title || b.base_name || '';
        break;
      case 'year':
        aValue = Math.max(...(a.years?.map(y => parseInt(y) || 0) || [0]));
        bValue = Math.max(...(b.years?.map(y => parseInt(y) || 0) || [0]));
        break;
      case 'province':
        aValue = a.provinces?.[0] || a.province || '';
        bValue = b.provinces?.[0] || b.province || '';
        break;
      case 'amendments':
        aValue = a.amendment_chain?.total_amendments || a.version_count || 0;
        bValue = b.amendment_chain?.total_amendments || b.version_count || 0;
        break;
      case 'confidence':
        aValue = a.group_confidence || a.constitutional_info?.confidence || 0;
        bValue = b.group_confidence || b.constitutional_info?.confidence || 0;
        break;
      default:
        aValue = a.title || a.base_name || '';
        bValue = b.title || b.base_name || '';
    }

    if (typeof aValue === 'string') {
      const comparison = aValue.localeCompare(bValue);
      return sortOptions.direction === 'asc' ? comparison : -comparison;
    } else {
      const comparison = aValue - bValue;
      return sortOptions.direction === 'asc' ? comparison : -comparison;
    }
  });

  return filtered;
};

// Statistics Panel Component
const StatisticsPanel: React.FC<{ 
  statistics?: GroupingStatistics;
  isLoading?: boolean;
  error?: string;
  onDetectChains?: () => void;
  onExportJson?: () => void;
  onExportCsv?: () => void;
}> = ({ statistics, isLoading, error, onDetectChains, onExportJson, onExportCsv }) => {
  if (isLoading) {
    return (
      <div className="bg-white p-4 rounded-lg border border-gray-200 mb-6">
        <div className="flex items-center justify-center py-4">
          <RefreshCw className="w-5 h-5 animate-spin text-blue-600" />
          <span className="ml-2 text-gray-600">Loading statistics...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 p-4 rounded-lg border border-red-200 mb-6">
        <div className="flex items-center text-red-800">
          <AlertCircle className="w-5 h-5 mr-2" />
          <span className="text-sm">Failed to load statistics: {error}</span>
        </div>
      </div>
    );
  }

  if (!statistics) {
    return (
      <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 mb-6">
        <div className="text-center text-gray-500">
          <BarChart3 className="w-8 h-8 mx-auto mb-2 text-gray-300" />
          <p className="text-sm">No statistics available</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white p-4 rounded-lg border border-gray-200 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center">
          <BarChart3 className="w-5 h-5 mr-2 text-blue-600" />
          Collection Statistics
        </h3>
        
        <div className="flex items-center space-x-2">
          {onDetectChains && (
            <button
              onClick={onDetectChains}
              className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
            >
              <FileText className="w-4 h-4 mr-1" />
              Detect Chains
            </button>
          )}
          {onExportJson && (
            <button
              onClick={onExportJson}
              className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
            >
              <Download className="w-4 h-4 mr-1" />
              JSON
            </button>
          )}
          {onExportCsv && (
            <button
              onClick={onExportCsv}
              className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
            >
              <Download className="w-4 h-4 mr-1" />
              CSV
            </button>
          )}
        </div>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-600">{statistics.total_statutes}</div>
          <div className="text-sm text-gray-600">Total Statutes</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-green-600">{statistics.constitutional_amendments || 0}</div>
          <div className="text-sm text-gray-600">Constitutional</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-purple-600">{statistics.amendment_chains || 0}</div>
          <div className="text-sm text-gray-600">Amendment Chains</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-orange-600">{statistics.province_distribution.length}</div>
          <div className="text-sm text-gray-600">Provinces</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Top Provinces</h4>
          <div className="space-y-1">
            {statistics.province_distribution.slice(0, 3).map((item, index) => (
              <div key={index} className="flex items-center justify-between text-sm">
                <span className="text-gray-600">{item.province}</span>
                <span className="font-medium">{item.count}</span>
              </div>
            ))}
          </div>
        </div>
        
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Statute Types</h4>
          <div className="space-y-1">
            {statistics.type_distribution.slice(0, 3).map((item, index) => (
              <div key={index} className="flex items-center justify-between text-sm">
                <span className="text-gray-600">{item.type}</span>
                <span className="font-medium">{item.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default function GroupedStatutesViewer({ 
  refreshTrigger, 
  selectedCollection,
  onRefresh 
}: GroupedStatutesViewerProps) {
  const [groups, setGroups] = useState<StatuteGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [loadingStatutes, setLoadingStatutes] = useState<Set<string>>(new Set());
  const [availableProvinces, setAvailableProvinces] = useState<string[]>([]);
  const [statistics, setStatistics] = useState<GroupingStatistics | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [detectedChains, setDetectedChains] = useState<AmendmentChain[]>([]);
  const [showChainList, setShowChainList] = useState(false);
  const [pagination, setPagination] = useState({
    page: 1,
    limit: 20,
    total: 0,
    pages: 0,
  });
  const [filters, setFilters] = useState<GroupingFilters>({
    searchTerm: '',
    selectedProvince: 'all',
    selectedYear: 'all',
    amendmentTypeFilter: 'all',
    constitutionalOnly: false,
    showChainOnly: false,
  });
  
  // Memoize filters to prevent unnecessary re-renders
  const memoizedFilters = useMemo(() => ({
    searchTerm: filters.searchTerm,
    selectedProvince: filters.selectedProvince,
    selectedYear: filters.selectedYear,
    amendmentTypeFilter: filters.amendmentTypeFilter,
    constitutionalOnly: filters.constitutionalOnly,
    showChainOnly: filters.showChainOnly
  }), [
    filters.searchTerm,
    filters.selectedProvince,
    filters.selectedYear,
    filters.amendmentTypeFilter,
    filters.constitutionalOnly,
    filters.showChainOnly
  ]);
  const [legacyFilters, setLegacyFilters] = useState({
    province: '',
    statute_type: '',
    base_name: '',
  });
  const [sortOptions, setSortOptions] = useState<SortOptions>({
    field: 'name',
    direction: 'asc'
  });

  // Memoized filtered and sorted groups
  const filteredGroups = useMemo(
    () => filterAndSortGroups(groups, memoizedFilters, sortOptions),
    [groups, memoizedFilters, sortOptions]
  );

  // Extract filter options from groups
  const availableYears = useMemo(() => {
    const years = new Set<string>();
    groups.forEach(group => {
      group.years?.forEach(y => years.add(y));
    });
    return Array.from(years).sort((a, b) => parseInt(b) - parseInt(a));
  }, [groups]);

  const availableAmendmentTypes = useMemo(() => {
    const types = new Set<string>();
    groups.forEach(group => {
      if (group.constitutional_info?.amendment_type) {
        types.add(group.constitutional_info.amendment_type);
      }
    });
    return Array.from(types).sort();
  }, [groups]);

  // Enhanced API functions with retry mechanisms
  const detectAmendmentChains = useCallback(async (retries = 3) => {
    if (!selectedCollection) return;
    
    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        const result = await Phase5ApiService.detectAmendmentChains(selectedCollection);
        setDetectedChains(result.chains || []);
        setShowChainList(true);
        return;
      } catch (error) {
        console.error(`Amendment chain detection attempt ${attempt} failed:`, error);
        if (attempt === retries) {
          setError(`Failed to detect amendment chains after ${retries} attempts`);
        } else {
          // Wait before retry with exponential backoff
          await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, attempt - 1)));
        }
      }
    }
  }, [selectedCollection]);

  const exportGroups = useCallback(async (format: 'json' | 'csv', retries = 3) => {
    if (!selectedCollection) return;
    
    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        const exportData = await Phase5ApiService.exportGroupsEnhanced(
          format,
          selectedCollection,
          true, // include analysis
          memoizedFilters
        );
        
        await Phase5ApiService.downloadExport(
          exportData,
          `phase5-groups-${selectedCollection}-${new Date().toISOString().split('T')[0]}`,
          format
        );
        return;
      } catch (error) {
        console.error(`Export attempt ${attempt} failed:`, error);
        if (attempt === retries) {
          setError(`Failed to export groups after ${retries} attempts`);
        } else {
          await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, attempt - 1)));
        }
      }
    }
  }, [selectedCollection, memoizedFilters]);

  // Load provinces on mount
  useEffect(() => {
    const loadProvinces = async () => {
      try {
        const response = await Phase5ApiService.getProvinces();
        setAvailableProvinces(response.provinces);
      } catch (error) {
        console.error('Failed to load provinces:', error);
        // Don't show error for provinces - it's not critical
      }
    };

    loadProvinces();
  }, []);

  // Load statistics when collection changes
  useEffect(() => {
    const loadStatistics = async () => {
      if (!selectedCollection) return;
      
      setStatsLoading(true);
      setStatsError(null);
      try {
        const stats = await Phase5ApiService.getCollectionStatistics(selectedCollection);
        setStatistics(stats);
      } catch (error) {
        console.error('Failed to load statistics:', error);
        setStatsError(error instanceof Error ? error.message : 'Unknown error');
      } finally {
        setStatsLoading(false);
      }
    };

    if (selectedCollection) {
      loadStatistics();
    }
  }, [selectedCollection]);

  // Memoize legacyFilters to prevent unnecessary re-renders
  const memoizedLegacyFilters = useMemo(() => ({
    province: legacyFilters.province,
    statute_type: legacyFilters.statute_type,
    base_name: legacyFilters.base_name
  }), [
    legacyFilters.province,
    legacyFilters.statute_type,
    legacyFilters.base_name
  ]);

  // Load groups - memoized to prevent unnecessary re-renders
  const loadGroups = useCallback(async (page: number = 1) => {
    try {
      setLoading(true);
      setError(null);
      
      // Use a fixed limit to prevent dependency cycles
      const limit = 20;
      
      const response: GroupsResponse = await Phase5ApiService.getGroups(
        page, 
        limit,
        {
          ...(memoizedLegacyFilters.province && { province: memoizedLegacyFilters.province }),
          ...(memoizedLegacyFilters.statute_type && { statute_type: memoizedLegacyFilters.statute_type }),
          ...(memoizedLegacyFilters.base_name && { base_name: memoizedLegacyFilters.base_name }),
        }
      );
      
      if (response.success) {
        // Ensure groups is always an array
        const groupsData = Array.isArray(response.groups) ? response.groups : [];
        setGroups(groupsData);
        
        setPagination(response.pagination || {
          page: 1,
          limit: 20,
          total: 0,
          pages: 0,
        });
        
        // Clear error if successful
        setError(null);
      } else {
        setError(response.message || 'Failed to load statute groups');
        setGroups([]); // Reset to empty array on error
      }
    } catch (err) {
      console.error('Error loading groups:', err);
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    } finally {
      setLoading(false);
    }
  }, [memoizedLegacyFilters]);

  // Load statutes for a specific group
  const loadGroupStatutes = async (groupId: string) => {
    try {
      setLoadingStatutes(prev => new Set(prev).add(groupId));
      
      const response = await Phase5ApiService.getGroupedStatutes(groupId);
      
      if (response.success) {
        setGroups(prevGroups => 
          prevGroups.map(group => 
            group.group_id === groupId 
              ? { ...group, statutes: response.statutes }
              : group
          )
        );
      }
    } catch (err) {
      console.error('Error loading group statutes:', err);
      setError(err instanceof Error ? err.message : 'Failed to load group statutes');
    } finally {
      setLoadingStatutes(prev => {
        const newSet = new Set(prev);
        newSet.delete(groupId);
        return newSet;
      });
    }
  };

  // Toggle group expansion
  const toggleGroup = async (groupId: string) => {
    const isExpanded = expandedGroups.has(groupId);
    const newExpanded = new Set(expandedGroups);
    
    if (isExpanded) {
      newExpanded.delete(groupId);
    } else {
      newExpanded.add(groupId);
      
      // Load statutes if not already loaded
      const group = groups.find(g => g.group_id === groupId);
      if (group && !group.statutes) {
        await loadGroupStatutes(groupId);
      }
    }
    
    setExpandedGroups(newExpanded);
  };

  // Export groups
  const handleExport = async (format: 'json' | 'csv') => {
    try {
      const blob = await Phase5ApiService.exportGroups(format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `statute-groups.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
      setError(err instanceof Error ? err.message : 'Export failed');
    }
  };

  // Load initial data
  useEffect(() => {
    loadGroups(1);
  }, [loadGroups, refreshTrigger]);

  // Filter change handler
  const handleFilterChange = (field: keyof typeof legacyFilters, value: string) => {
    setLegacyFilters(prev => ({
      ...prev,
      [field]: value,
    }));
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  if (loading && (!groups || groups.length === 0)) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-8">
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          <span className="ml-3 text-gray-600">Loading statute groups...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="text-center">
          <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Error Loading Groups</h3>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={() => loadGroups(pagination?.page || 1)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Statistics panel */}
      {selectedCollection && (
        <StatisticsPanel 
          statistics={statistics || undefined} 
          isLoading={statsLoading} 
          error={statsError || undefined}
          onDetectChains={detectAmendmentChains}
          onExportJson={() => exportGroups('json')}
          onExportCsv={() => exportGroups('csv')}
        />
      )}

      {/* Amendment chains modal */}
      {showChainList && (
        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Amendment Chains</h3>
            <button
              onClick={() => setShowChainList(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              ×
            </button>
          </div>
          <AmendmentChainList 
            chains={detectedChains}
            onChainSelect={(chain) => console.log('Selected chain:', chain)}
          />
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-lg">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            Grouped Statutes
            {pagination?.total && pagination.total > 0 && (
              <span className="ml-2 text-sm font-normal text-gray-500">
                ({pagination.total.toLocaleString()} groups)
              </span>
            )}
          </h2>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleExport('json')}
              className="flex items-center px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
            >
              <Download className="h-4 w-4 mr-1" />
              JSON
            </button>
            <button
              onClick={() => handleExport('csv')}
              className="flex items-center px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
            >
              <Download className="h-4 w-4 mr-1" />
              CSV
            </button>
          </div>
        </div>

        {/* Enhanced Search and Filter Controls */}
        <div className="space-y-4">
          {/* Search Bar */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search Groups
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search by name, province, type, or constitutional base..."
                value={filters.searchTerm}
                onChange={(e) => setFilters(prev => ({ ...prev, searchTerm: e.target.value }))}
                className="pl-10 w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          {/* Filter Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Province
              </label>
              <select
                value={filters.selectedProvince}
                onChange={(e) => setFilters(prev => ({ ...prev, selectedProvince: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="all">All Provinces</option>
                {availableProvinces.map((province) => (
                  <option key={province} value={province}>
                    {province}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Year
              </label>
              <select
                value={filters.selectedYear}
                onChange={(e) => setFilters(prev => ({ ...prev, selectedYear: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="all">All Years</option>
                {availableYears.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Amendment Type
              </label>
              <select
                value={filters.amendmentTypeFilter}
                onChange={(e) => setFilters(prev => ({ ...prev, amendmentTypeFilter: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="all">All Types</option>
                {availableAmendmentTypes.map((type) => (
                  <option key={type} value={type}>
                    {type.charAt(0).toUpperCase() + type.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Sort By
              </label>
              <div className="flex space-x-1">
                <select
                  value={sortOptions.field}
                  onChange={(e) => setSortOptions(prev => ({ ...prev, field: e.target.value as any }))}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="name">Name</option>
                  <option value="year">Year</option>
                  <option value="province">Province</option>
                  <option value="amendments">Amendments</option>
                  <option value="confidence">Confidence</option>
                </select>
                <button
                  onClick={() => setSortOptions(prev => ({ 
                    ...prev, 
                    direction: prev.direction === 'asc' ? 'desc' : 'asc' 
                  }))}
                  className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50 transition-colors"
                  title={`Sort ${sortOptions.direction === 'asc' ? 'ascending' : 'descending'}`}
                >
                  {sortOptions.direction === 'asc' ? '↑' : '↓'}
                </button>
              </div>
            </div>
          </div>

          {/* Filter Checkboxes */}
          <div className="flex items-center space-x-6">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={filters.constitutionalOnly}
                onChange={(e) => setFilters(prev => ({ ...prev, constitutionalOnly: e.target.checked }))}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">Constitutional only</span>
            </label>

            <label className="flex items-center">
              <input
                type="checkbox"
                checked={filters.showChainOnly}
                onChange={(e) => setFilters(prev => ({ ...prev, showChainOnly: e.target.checked }))}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">Amendment chains only</span>
            </label>

            <button
              onClick={() => setFilters({
                searchTerm: '',
                selectedProvince: 'all',
                selectedYear: 'all',
                amendmentTypeFilter: 'all',
                constitutionalOnly: false,
                showChainOnly: false,
              })}
              className="px-3 py-1 text-sm text-blue-600 hover:text-blue-800 border border-blue-300 rounded hover:bg-blue-50 transition-colors"
            >
              Clear all filters
            </button>
          </div>

          {/* Legacy Filters for Backward Compatibility */}
          <div className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-200">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Legacy Search by Name
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Enter statute name..."
                  value={legacyFilters.base_name}
                  onChange={(e) => handleFilterChange('base_name', e.target.value)}
                  className="pl-10 w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Legacy Province
              </label>
              <select
                value={legacyFilters.province}
                onChange={(e) => handleFilterChange('province', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All Provinces</option>
                {availableProvinces.map((province) => (
                  <option key={province} value={province}>
                    {province}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Legacy Statute Type
              </label>
              <input
                type="text"
                placeholder="e.g., Act, Regulation..."
                value={legacyFilters.statute_type}
                onChange={(e) => handleFilterChange('statute_type', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Results Summary */}
      <div className="px-6 py-3 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>
            Showing {filteredGroups.length} of {groups.length} groups
            {filteredGroups.length !== groups.length && (
              <span className="text-blue-600 ml-1">(filtered)</span>
            )}
          </span>
          <span>
            {filteredGroups.reduce((sum, group) => sum + (group.total_statutes || group.version_count || group.statutes?.length || 0), 0)} total statutes
          </span>
        </div>
      </div>

      {/* Groups List */}
      <div className="divide-y divide-gray-200">
        {!groups || groups.length === 0 ? (
          <div className="p-8 text-center">
            <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {loading ? 'Loading Groups...' : 'No Grouped Statutes Available'}
            </h3>
            <p className="text-gray-600">
              {loading 
                ? 'Please wait while we load the statute groups.'
                : Object.values(legacyFilters).some(f => f) 
                  ? 'Try adjusting your filters to see more results.' 
                  : 'Run the grouping process to create statute groups from your documents.'}
            </p>
          </div>
        ) : filteredGroups.length === 0 ? (
          <div className="p-8 text-center">
            <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Groups Match Your Filters</h3>
            <p className="text-gray-600 mb-4">
              Try adjusting your search terms or filter settings to find groups.
            </p>
            <button
              onClick={() => setFilters({
                searchTerm: '',
                selectedProvince: 'all',
                selectedYear: 'all',
                amendmentTypeFilter: 'all',
                constitutionalOnly: false,
                showChainOnly: false,
              })}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              Clear All Filters
            </button>
          </div>
        ) : (
          filteredGroups.map((group) => (
            <GroupAccordion
              key={group.group_id || group.id}
              group={group}
              isExpanded={expandedGroups.has(group.group_id || group.id || '')}
              isLoadingStatutes={loadingStatutes.has(group.group_id || group.id || '')}
              onToggle={() => toggleGroup(group.group_id || group.id || '')}
            />
          ))
        )}
      </div>

      {/* Pagination */}
      {pagination?.pages && pagination.pages > 1 && (
        <div className="p-4 border-t border-gray-200 flex items-center justify-between">
          <div className="text-sm text-gray-700">
            Showing page {pagination.page || 1} of {pagination.pages || 1}
          </div>
          <div className="flex space-x-2">
            <button
              onClick={() => loadGroups((pagination.page || 1) - 1)}
              disabled={(pagination.page || 1) <= 1 || loading}
              className="px-3 py-2 text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              onClick={() => loadGroups((pagination.page || 1) + 1)}
              disabled={(pagination.page || 1) >= (pagination.pages || 1) || loading}
              className="px-3 py-2 text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

interface GroupAccordionProps {
  group: StatuteGroup;
  isExpanded: boolean;
  isLoadingStatutes: boolean;
  onToggle: () => void;
}

function GroupAccordion({ group, isExpanded, isLoadingStatutes, onToggle }: GroupAccordionProps) {
  // Enhanced group properties from intelligent analysis
  const hasAmendmentChain = group.amendment_chain && group.amendment_chain.members && group.amendment_chain.members.length > 1;
  const isConstitutional = group.constitutional_info?.is_constitutional || false;
  const hasIntelligentAnalysis = group.constitutional_info || group.amendment_chain;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm hover:shadow-md transition-shadow">
      {/* Enhanced Group Header */}
      <button
        onClick={onToggle}
        className="w-full p-4 text-left bg-gray-50 hover:bg-gray-100 focus:outline-none focus:bg-gray-100 transition-colors"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            {isExpanded ? (
              <ChevronDown className="h-5 w-5 text-gray-400" />
            ) : (
              <ChevronRight className="h-5 w-5 text-gray-400" />
            )}
            <div className="flex-1">
              <div className="flex items-center mb-2">
                <h3 className="text-lg font-semibold text-gray-900 mr-3">{group.base_name}</h3>
                
                {/* Enhanced Badges */}
                <div className="flex items-center space-x-2">
                  {isConstitutional && (
                    <div className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
                      <Shield className="w-3 h-3 mr-1" />
                      Constitutional
                    </div>
                  )}
                  
                  {hasAmendmentChain && (
                    <div className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-purple-100 text-purple-800 border border-purple-200">
                      <FileText className="w-3 h-3 mr-1" />
                      {group.amendment_chain?.total_amendments} Amendments
                    </div>
                  )}

                  {hasIntelligentAnalysis && (
                    <div className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-green-100 text-green-800 border border-green-200">
                      <CheckCircle2 className="w-3 h-3 mr-1" />
                      AI Analyzed
                    </div>
                  )}
                </div>
              </div>

              {/* Enhanced Group metadata */}
              <div className="flex items-center space-x-4 text-sm text-gray-600">
                <div className="flex items-center">
                  <FileText className="h-4 w-4 mr-1" />
                  {group.version_count} version{group.version_count !== 1 ? 's' : ''}
                </div>
                
                {group.province && (
                  <div className="flex items-center">
                    <MapPin className="h-4 w-4 mr-1" />
                    {group.province}
                  </div>
                )}
                
                {group.statute_type && (
                  <div className="flex items-center">
                    <Tag className="h-4 w-4 mr-1" />
                    {group.statute_type}
                  </div>
                )}

                {group.group_confidence && group.group_confidence > 0 && (
                  <div className="flex items-center">
                    <CheckCircle2 className="w-4 h-4 mr-1" />
                    {Math.round(group.group_confidence * 100)}% confidence
                  </div>
                )}
              </div>
            </div>
          </div>
          
          <div className="text-xs text-gray-500">
            {new Date(group.created_at).toLocaleDateString()}
          </div>
        </div>
      </button>

      {/* Enhanced Group Details */}
      {isExpanded && (
        <div className="p-4 border-t border-gray-200">
          {isLoadingStatutes ? (
            <div className="flex items-center justify-center py-4">
              <RefreshCw className="w-5 h-5 animate-spin text-blue-500 mr-2" />
              <span className="text-gray-600">Loading statutes...</span>
            </div>
          ) : group.statutes && group.statutes.length > 0 ? (
            <div className="space-y-3 mb-4">
              <h4 className="font-medium text-gray-900">Statutes ({group.statutes.length})</h4>
              {group.statutes
                .sort((a, b) => a.version_number - b.version_number)
                .map((statute) => (
                  <StatuteCard key={statute._id} statute={statute} />
                ))}
            </div>
          ) : (
            <div className="text-gray-500 text-sm mb-4">No statutes loaded for this group</div>
          )}

          {/* Amendment chain visualization */}
          {hasAmendmentChain && (
            <div className="mt-4">
              <AmendmentChainViewer
                chain={group.amendment_chain}
                constitutionalAnalysis={group.constitutional_info}
                isExpanded={true}
                showFullDetails={false}
              />
            </div>
          )}

          {/* Constitutional analysis display */}
          {group.constitutional_info && !hasAmendmentChain && (
            <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
              <h5 className="font-medium text-blue-900 mb-2">Constitutional Analysis</h5>
              <div className="text-sm text-blue-800">
                <p><strong>Type:</strong> {group.constitutional_info.amendment_type || 'Not specified'}</p>
                <p><strong>Base:</strong> {group.constitutional_info.constitutional_base || 'Not specified'}</p>
                {group.constitutional_info.target_articles && group.constitutional_info.target_articles.length > 0 && (
                  <p className="mt-1">
                    <strong>Target Articles:</strong> {group.constitutional_info.target_articles.slice(0, 3).join(', ')}
                    {group.constitutional_info.target_articles.length > 3 && ` +${group.constitutional_info.target_articles.length - 3} more`}
                  </p>
                )}
                <p className="mt-1">
                  <strong>Confidence:</strong> {Math.round((group.constitutional_info.confidence || 0) * 100)}%
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface StatuteCardProps {
  statute: GroupedStatute;
}

function StatuteCard({ statute }: StatuteCardProps) {
  return (
    <div className={`p-3 bg-white border rounded-md ${statute.is_base_version ? 'border-blue-200 bg-blue-50' : 'border-gray-200'}`}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2">
            <span className={`text-sm font-medium ${statute.is_base_version ? 'text-blue-900' : 'text-gray-900'}`}>
              Version {statute.version_number}
              {statute.is_base_version && (
                <span className="ml-2 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded-full">
                  Base
                </span>
              )}
            </span>
            {statute.similarity_score && (
              <span className="text-xs text-gray-500">
                ({(statute.similarity_score * 100).toFixed(1)}% similarity)
              </span>
            )}
          </div>
          {statute.date_enacted && (
            <div className="flex items-center text-xs text-gray-600 mt-1">
              <Calendar className="h-3 w-3 mr-1" />
              {new Date(statute.date_enacted).toLocaleDateString()}
            </div>
          )}
        </div>
        <div className="text-xs text-gray-500">
          {statute.statute_data?.title || 'No title'}
        </div>
      </div>
    </div>
  );
}
