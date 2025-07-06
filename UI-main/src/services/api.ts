const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://your-backend-app-name.onrender.com';

export interface SearchRequest {
  space_key: string;
  page_titles: string[];
  query: string;
}

export interface CodeRequest {
  space_key: string;
  page_title: string;
  instruction: string;
  target_language?: string;
}

export interface ImpactRequest {
  space_key: string;
  old_page_title: string;
  new_page_title: string;
  question?: string;
}

export interface TestRequest {
  space_key: string;
  code_page_title: string;
  test_input_page_title?: string;
  question?: string;
}

export interface ExportRequest {
  content: string;
  format: string;
  filename: string;
}

export interface Space {
  name: string;
  key: string;
}

export interface SearchResponse {
  response: string;
  pages_analyzed: number;
  page_titles: string[];
}

export interface CodeResponse {
  summary: string;
  original_code: string;
  detected_language: string;
  modified_code?: string;
  converted_code?: string;
  target_language?: string;
}

export interface ImpactResponse {
  lines_added: number;
  lines_removed: number;
  files_changed: number;
  percentage_change: number;
  impact_analysis: string;
  recommendations: string;
  risk_analysis: string;
  risk_level: string;
  risk_score: number;
  risk_factors: string[];
  answer?: string;
  diff: string;
}

export interface TestResponse {
  test_strategy: string;
  cross_platform_testing: string;
  sensitivity_analysis?: string;
  ai_response?: string;
}

export interface ExportResponse {
  file: string;
  mime: string;
  filename: string;
}

export interface VideoRequest {
  video_url?: string;
  space_key: string;
  page_title: string;
  question?: string;
}

export interface VideoResponse {
  summary: string;
  quotes: string[];
  timestamps?: string[];
  qa: Array<{question: string, answer: string}>;
  page_title: string;
  answer?: string;
}

export interface ImageRequest {
  space_key: string;
  page_title: string;
  image_url: string;
}

export interface ImageSummaryRequest {
  space_key: string;
  page_title: string;
  image_url: string;
  summary: string;
  question: string;
}

export interface ChartRequest {
  space_key: string;
  page_title: string;
  image_url: string;
  chart_type: string;
  filename: string;
  format: string;
}

export interface ImageResponse {
  summary: string;
}

export interface ImageQAResponse {
  answer: string;
}

export interface ChartResponse {
  chart_data: string;
  mime_type: string;
  filename: string;
}

class ApiService {
  private async makeRequest<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'API request failed');
    }

    return response.json();
  }

  async getSpaces(): Promise<{ spaces: Space[] }> {
    return this.makeRequest<{ spaces: Space[] }>('/spaces');
  }

  async getPages(spaceKey: string): Promise<{ pages: string[] }> {
    return this.makeRequest<{ pages: string[] }>(`/pages/${spaceKey}`);
  }

  async search(request: SearchRequest): Promise<SearchResponse> {
    return this.makeRequest<SearchResponse>('/search', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async videoSummarizer(request: VideoRequest): Promise<VideoResponse> {
    return this.makeRequest<VideoResponse>('/video-summarizer', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async codeAssistant(request: CodeRequest): Promise<CodeResponse> {
    return this.makeRequest<CodeResponse>('/code-assistant', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async impactAnalyzer(request: ImpactRequest): Promise<ImpactResponse> {
    return this.makeRequest<ImpactResponse>('/impact-analyzer', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async testSupport(request: TestRequest): Promise<TestResponse> {
    return this.makeRequest<TestResponse>('/test-support', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getImages(spaceKey: string, pageTitle: string): Promise<{ images: string[] }> {
    return this.makeRequest<{ images: string[] }>(`/images/${spaceKey}/${encodeURIComponent(pageTitle)}`);
  }

  async imageSummary(request: ImageRequest): Promise<ImageResponse> {
    return this.makeRequest<ImageResponse>('/image-summary', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async imageQA(request: ImageSummaryRequest): Promise<ImageQAResponse> {
    return this.makeRequest<ImageQAResponse>('/image-qa', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async createChart(request: ChartRequest): Promise<ChartResponse> {
    return this.makeRequest<ChartResponse>('/create-chart', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async exportContent(request: ExportRequest): Promise<Blob> {
    const response = await fetch(`${API_BASE_URL}/export`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Export failed');
    }

    const result = await response.json();
    
    // Handle binary files (PDF, DOCX) that are base64 encoded
    if (request.format === 'pdf' || request.format === 'docx') {
      const binaryString = atob(result.file);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      return new Blob([bytes], { type: result.mime });
    } else {
      // Handle text files
      const encoder = new TextEncoder();
      const bytes = encoder.encode(result.file);
      return new Blob([bytes], { type: result.mime });
    }
  }
}

export const apiService = new ApiService(); 