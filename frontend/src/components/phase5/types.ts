// Phase 5 TypeScript interfaces and types

export interface Phase5Status {
  current_phase: string;
  status: string;
  is_processing: boolean;
  source_database?: string;
  target_database?: string;
  source_collections?: number;
  total_source_documents?: number;
  grouped_documents?: number;
  azure_openai_configured?: boolean;
  deployment_name?: string;
  current_progress?: number;
}

export interface GroupingProgress {
  status: 'fetching' | 'fetching_complete' | 'grouping' | 'grouping_complete' | 'versioning' | 'completed' | 'error';
  progress: number;
  message: string;
  total_statutes?: number;
  total_groups?: number;
  total_versioned?: number;
  error?: string;
  timestamp?: string;
}

export interface StatuteGroup {
  group_id: string;
  base_name: string;
  province: string | null;
  statute_type: string | null;
  legal_category: string | null;
  version_count: number;
  base_statute_id: string;
  created_at: string;
  statutes?: GroupedStatute[];
  
  // Enhanced intelligent analysis properties
  id?: string; // For compatibility with new analysis features
  title?: string; // Enhanced title from analysis
  provinces?: string[]; // Multiple provinces support
  years?: string[]; // Years extracted from analysis
  total_statutes?: number; // Total count for display
  group_confidence?: number; // AI confidence score
  constitutional_info?: ConstitutionalAnalysis; // Constitutional analysis results
  amendment_chain?: AmendmentChain; // Amendment chain information
}

export interface GroupedStatute {
  _id: string;
  original_statute_id: string;
  group_id: string;
  base_name: string;
  province: string | null;
  statute_type: string | null;
  legal_category: string | null;
  version_number: number;
  is_base_version: boolean;
  date_enacted: string | null;
  similarity_score: number | null;
  statute_data: any;
  created_at: string;
  updated_at: string;
}

export interface GroupingConfig {
  source_database?: string;
  target_database?: string;
  target_collection?: string;
  similarity_threshold?: number;
  batch_size?: number;
  use_azure_openai?: boolean;
}

export interface StartGroupingRequest {
  config?: GroupingConfig;
  source_collections?: string[];
}

export interface StartGroupingResponse {
  success: boolean;
  message?: string;
  task_id?: string;
  total_statutes?: number;
  estimated_groups?: number;
}

export interface GroupsResponse {
  success: boolean;
  message?: string;
  groups?: StatuteGroup[];
  pagination?: {
    page: number;
    limit: number;
    total: number;
    pages: number;
  };
}

export interface GroupedStatutesResponse {
  success: boolean;
  message?: string;
  statutes?: GroupedStatute[];
  pagination?: {
    page: number;
    limit: number;
    total: number;
    pages: number;
  };
}

// ===== ENHANCED INTELLIGENT ANALYSIS TYPES =====

export interface Statute {
  _id: string;
  Statute_Name: string;
  Province?: string;
  Year?: string;
  Date?: string;
  Statute_Type?: string;
  Preamble?: string;
  Sections?: Section[];
  base_name?: string;
  Version_Label?: string;
  // Enhanced analysis fields
  constitutional_analysis?: ConstitutionalAnalysis;
  legal_context?: LegalContext;
  amendment_chains?: AmendmentChain[];
}

export interface Section {
  Section?: string;
  Definition?: string;
  text?: string;
}

export interface ConstitutionalAnalysis {
  is_constitutional: boolean;
  constitutional_base: string;
  amendment_number: string;
  amendment_type: 'amendment' | 'repeal' | 'addition' | 'order' | 'none';
  target_articles: string[];
  confidence: number;
  analysis_method?: 'gpt' | 'rule_based' | 'fallback';
}

export interface LegalContext {
  legal_references: string[];
  amendment_targets: string[];
  relationship_types: string[];
  legal_hierarchy: string;
  confidence: number;
  analysis_method?: 'gpt' | 'rule_based' | 'fallback';
}

export interface AmendmentChain {
  chain_id: string;
  base_name: string;
  members: AmendmentMember[];
  total_amendments: number;
  creation_date: string;
}

export interface AmendmentMember {
  statute_id: string;
  statute_name: string;
  date: string;
  position: number;
  amendment_type: string;
}

// ===== ENHANCED RESPONSE TYPES =====

export interface CollectionsResponse {
  success: boolean;
  message: string;
  data: {
    collections: string[];
  };
}

export interface ProvincesResponse {
  success: boolean;
  message: string;
  data: {
    provinces: string[];
  };
}

export interface AnalyzeStatuteRequest {
  statute: Statute;
}

export interface AnalyzeStatuteResponse {
  success: boolean;
  message: string;
  data: {
    constitutional_analysis: ConstitutionalAnalysis;
    legal_context: LegalContext;
    statute_id: string;
    analysis_timestamp: string;
  };
}

export interface DetectChainsRequest {
  collection_name: string;
}

export interface DetectChainsResponse {
  success: boolean;
  message: string;
  data: {
    chains: AmendmentChain[];
    total_chains: number;
    collection_name: string;
    analysis_timestamp: string;
  };
}

export interface GroupingStatistics {
  total_statutes: number;
  province_distribution: Array<{ province: string; count: number }>;
  type_distribution: Array<{ type: string; count: number }>;
  year_distribution: Array<{ year: string; count: number }>;
  collection_name: string;
  timestamp: string;
  constitutional_amendments?: number;
  amendment_chains?: number;
}

export interface StatisticsResponse {
  success: boolean;
  message: string;
  data: GroupingStatistics;
}

// ===== UI STATE TYPES =====

export interface GroupingFilters {
  searchTerm: string;
  selectedProvince: string;
  selectedYear: string;
  amendmentTypeFilter: string;
  constitutionalOnly: boolean;
  showChainOnly: boolean;
}

export interface SortOptions {
  field: 'name' | 'year' | 'province' | 'amendments' | 'confidence';
  direction: 'asc' | 'desc';
}

export interface ExportRequest {
  format: 'json' | 'csv';
  collection_name: string;
  include_analysis: boolean;
  filters?: GroupingFilters;
}

export interface ExportResponse {
  success: boolean;
  message: string;
  data: {
    export_timestamp: string;
    collection_name: string;
    format: string;
    include_analysis: boolean;
    groups: StatuteGroup[];
    metadata: {
      total_groups: number;
      total_statutes: number;
      export_version: string;
    };
  };
}
