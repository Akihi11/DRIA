import axios, { AxiosInstance, AxiosResponse } from 'axios'
import { 
  DialogueRequest, 
  DialogueResponse,
  FileUploadResponse,
  ReportGenerationRequest,
  ReportGenerationResponse,
  HealthCheckResponse
} from '../types/api'

class ApiService {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: '/api',
      timeout: 60000, // 60 seconds for report generation
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        console.log(`Making ${config.method?.toUpperCase()} request to ${config.url}`)
        return config
      },
      (error) => {
        console.error('Request error:', error)
        return Promise.reject(error)
      }
    )

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => {
        console.log(`Response received from ${response.config.url}:`, response.status)
        return response
      },
      (error) => {
        console.error('Response error:', error.response?.data || error.message)
        return Promise.reject(error)
      }
    )
  }

  // Health check
  async healthCheck(): Promise<HealthCheckResponse> {
    const response: AxiosResponse<HealthCheckResponse> = await this.client.get('/health')
    return response.data
  }

  // File upload
  async uploadFile(file: File): Promise<FileUploadResponse> {
    const formData = new FormData()
    formData.append('file', file)

    const response: AxiosResponse<any> = await this.client.post(
      '/ai_report/upload', 
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            console.log(`Upload progress: ${progress}%`)
          }
        },
      }
    )
    
    // Convert backend response format to match FileInfo interface
    const data = response.data
    return {
      file_id: data.file_id,
      filename: data.filename,
      size: data.file_size || data.size,  // Support both field names
      upload_time: data.upload_time,
      available_channels: data.available_channels || []
    }
  }

  // Dialogue interaction
  async processDialogue(request: DialogueRequest): Promise<DialogueResponse> {
    const response: AxiosResponse<DialogueResponse> = await this.client.post(
      '/ai_report/dialogue',
      request
    )
    return response.data
  }

  // Report generation
  async generateReport(request: ReportGenerationRequest): Promise<ReportGenerationResponse> {
    const response: AxiosResponse<ReportGenerationResponse> = await this.client.post(
      '/reports/generate',
      request
    )
    return response.data
  }

  // Download report
  async downloadReport(reportId: string): Promise<Blob> {
    const response: AxiosResponse<Blob> = await this.client.get(
      `/reports/download/${reportId}`,
      {
        responseType: 'blob',
      }
    )
    return response.data
  }

  // Get file info
  async getFileInfo(fileId: string): Promise<FileUploadResponse> {
    const response: AxiosResponse<FileUploadResponse> = await this.client.get(
      `/ai_report/file/${fileId}`
    )
    return response.data
  }

  // Get file channels with statistics
  async getFileChannels(fileId: string): Promise<any> {
    const response: AxiosResponse<any> = await this.client.get(
      `/analysis/channels/${fileId}`
    )
    return response.data
  }

  // Get reports list
  async listReports(sessionId?: string): Promise<any> {
    const response: AxiosResponse<any> = await this.client.get(
      '/reports',
      {
        params: sessionId ? { session_id: sessionId } : {}
      }
    )
    return response.data
  }

  // Report configuration APIs
  async startReportConfig(sessionId: string, reportType: string): Promise<any> {
    const response: AxiosResponse<any> = await this.client.post(
      '/report_config/start',
      {
        session_id: sessionId,
        report_type: reportType
      }
    )
    return response.data
  }

  async updateReportConfig(sessionId: string, action: string, value?: any): Promise<any> {
    const response: AxiosResponse<any> = await this.client.post(
      '/report_config/update',
      {
        session_id: sessionId,
        action: action,
        value: value
      }
    )
    return response.data
  }

  async getConfigStatus(sessionId: string): Promise<any> {
    const response: AxiosResponse<any> = await this.client.get(
      `/report_config/status/${sessionId}`
    )
    return response.data
  }
}

// Create singleton instance
export const apiService = new ApiService()
export default apiService
