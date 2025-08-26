// Phase 5 API service for statute grouping operations

import type { 
  Phase5Status, 
  StartGroupingRequest, 
  StartGroupingResponse,
  GroupsResponse,
  GroupedStatutesResponse
} from './types';

const API_BASE = 'http://localhost:8000/api/v1/phase5';

export class Phase5ApiService {
  private static getAuthToken(): string | null {
    return localStorage.getItem('token');
  }

  private static async makeRequest<T>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getAuthToken();
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...options.headers,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(errorData.detail || `Request failed: ${response.statusText}`);
    }

    return response.json();
  }

  // Get current Phase 5 status
  static async getStatus(collection?: string): Promise<Phase5Status> {
    const params = collection ? `?collection=${encodeURIComponent(collection)}` : '';
    return this.makeRequest<Phase5Status>(`/status${params}`);
  }

  // Start the grouping process
  static async startGrouping(request: StartGroupingRequest = {}): Promise<StartGroupingResponse> {
    return this.makeRequest<StartGroupingResponse>('/start-grouping', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Get progress stream using Server-Sent Events
  static createProgressStream(): EventSource {
    const token = this.getAuthToken();
    const url = new URL(`${API_BASE}/progress-stream`);
    if (token) {
      url.searchParams.append('token', token);
    }
    return new EventSource(url.toString());
  }

  // Get grouped statutes (paginated)
  static async getGroups(
    page: number = 1, 
    limit: number = 20,
    filters?: {
      province?: string;
      statute_type?: string;
      base_name?: string;
    }
  ): Promise<GroupsResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });

    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.append(key, value);
      });
    }

    return this.makeRequest<GroupsResponse>(`/groups?${params}`);
  }

  // Get statutes within a specific group
  static async getGroupedStatutes(
    groupId: string,
    page: number = 1,
    limit: number = 20
  ): Promise<GroupedStatutesResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });

    return this.makeRequest<GroupedStatutesResponse>(`/groups/${groupId}/statutes?${params}`);
  }

  // Clear all grouping data (for development/testing)
  static async clearGroups(): Promise<{ success: boolean; message: string }> {
    return this.makeRequest('/clear', {
      method: 'POST',
    });
  }

  // Get grouping statistics
  static async getStatistics(): Promise<{
    total_groups: number;
    total_statutes: number;
    groups_by_province: Record<string, number>;
    groups_by_type: Record<string, number>;
    average_versions_per_group: number;
  }> {
    return this.makeRequest('/statistics');
  }

  // Export grouped data
  static async exportGroups(format: 'json' | 'csv' = 'json'): Promise<Blob> {
    const token = this.getAuthToken();
    const response = await fetch(`${API_BASE}/export?format=${format}`, {
      headers: {
        ...(token && { 'Authorization': `Bearer ${token}` }),
      },
    });

    if (!response.ok) {
      throw new Error(`Export failed: ${response.statusText}`);
    }

    return response.blob();
  }

  // Get available collections
  static async getCollections(): Promise<{ collections: string[] }> {
    const response = await this.makeRequest<{ success: boolean; data: { collections: string[] } }>('/collections');
    return response.data;
  }

  // Get available provinces
  static async getProvinces(): Promise<{ provinces: string[] }> {
    const response = await this.makeRequest<{ success: boolean; data: { provinces: string[] } }>('/provinces');
    return response.data;
  }

  // ===== ENHANCED INTELLIGENT ANALYSIS METHODS =====

  // Analyze a single statute for constitutional lineage and legal context
  static async analyzeStatute(statute: any): Promise<{
    constitutional_analysis: any;
    legal_context: any;
    statute_id: string;
    analysis_timestamp: string;
  }> {
    const response = await this.makeRequest<{ 
      success: boolean; 
      data: {
        constitutional_analysis: any;
        legal_context: any;
        statute_id: string;
        analysis_timestamp: string;
      }
    }>('/analyze-statute', {
      method: 'POST',
      body: JSON.stringify({ statute }),
    });
    return response.data;
  }

  // Detect amendment chains in a collection
  static async detectAmendmentChains(collectionName: string): Promise<{
    chains: any[];
    total_chains: number;
    collection_name: string;
    analysis_timestamp: string;
  }> {
    const response = await this.makeRequest<{ 
      success: boolean; 
      data: {
        chains: any[];
        total_chains: number;
        collection_name: string;
        analysis_timestamp: string;
      }
    }>('/detect-amendment-chains', {
      method: 'POST',
      body: JSON.stringify({ collection_name: collectionName }),
    });
    return response.data;
  }

  // Get detailed statistics for a collection
  static async getCollectionStatistics(collectionName: string): Promise<{
    total_statutes: number;
    province_distribution: Array<{ province: string; count: number }>;
    type_distribution: Array<{ type: string; count: number }>;
    year_distribution: Array<{ year: string; count: number }>;
    collection_name: string;
    timestamp: string;
    constitutional_amendments?: number;
    amendment_chains?: number;
  }> {
    const response = await this.makeRequest<{ 
      success: boolean; 
      data: any 
    }>(`/statistics/${encodeURIComponent(collectionName)}`);
    return response.data;
  }

  // Export groups with enhanced options
  static async exportGroupsEnhanced(
    format: 'json' | 'csv',
    collectionName: string,
    includeAnalysis: boolean = false,
    filters?: any
  ): Promise<{
    export_timestamp: string;
    collection_name: string;
    format: string;
    include_analysis: boolean;
    groups: any[];
    metadata: {
      total_groups: number;
      total_statutes: number;
      export_version: string;
    };
  }> {
    const response = await this.makeRequest<{ 
      success: boolean; 
      data: any 
    }>('/export-groups', {
      method: 'POST',
      body: JSON.stringify({
        format,
        collection_name: collectionName,
        include_analysis: includeAnalysis,
        filters
      }),
    });
    return response.data;
  }

  // Batch analyze multiple statutes
  static async batchAnalyzeStatutes(statutes: any[], batchSize: number = 5): Promise<any[]> {
    const results = [];
    
    for (let i = 0; i < statutes.length; i += batchSize) {
      const batch = statutes.slice(i, i + batchSize);
      const batchPromises = batch.map(statute => 
        this.analyzeStatute(statute).catch(error => {
          console.warn(`Failed to analyze statute ${statute._id}:`, error);
          return null; // Return null for failed analyses
        })
      );
      
      const batchResults = await Promise.all(batchPromises);
      results.push(...batchResults.filter(result => result !== null));
      
      // Add small delay between batches to avoid overwhelming the API
      if (i + batchSize < statutes.length) {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    }
    
    return results;
  }

  // Download file helper for exports
  static async downloadExport(exportData: any, filename: string, format: 'json' | 'csv'): Promise<void> {
    try {
      let content: string;
      let mimeType: string;

      if (format === 'json') {
        content = JSON.stringify(exportData, null, 2);
        mimeType = 'application/json';
      } else { // csv
        content = this.convertToCSV(exportData.groups || exportData);
        mimeType = 'text/csv';
      }

      const blob = new Blob([content], { type: mimeType });
      const url = window.URL.createObjectURL(blob);
      
      const link = document.createElement('a');
      link.href = url;
      link.download = `${filename}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download export:', error);
      throw error;
    }
  }

  // Convert data to CSV format
  private static convertToCSV(data: any[]): string {
    if (!data || !Array.isArray(data) || data.length === 0) {
      return '';
    }

    // Get headers from first object
    const headers = Object.keys(data[0]);
    const csvRows = [];

    // Add header row
    csvRows.push(headers.join(','));

    // Add data rows
    for (const row of data) {
      const values = headers.map(header => {
        const value = row[header];
        // Handle values that might contain commas or quotes
        if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return value || '';
      });
      csvRows.push(values.join(','));
    }

    return csvRows.join('\n');
  }
}
