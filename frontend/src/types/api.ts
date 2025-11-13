// API Request/Response Types - 简化为纯对话
export interface DialogueRequest {
  session_id: string
  user_input: string
  dialogue_state: DialogueState
}

export interface DialogueResponse {
  session_id: string
  ai_response: string
  dialogue_state: DialogueState
  suggested_actions?: string[]
  is_complete: boolean
  error_message?: string
}

export interface FileUploadRequest {
  file: File
  session_id: string
}

export interface FileUploadResponse {
  file_id: string
  filename: string
  size: number
  file_size?: number  // Optional field for component compatibility
  upload_time: string
  available_channels: string[]
}

export interface ReportGenerationRequest {
  session_id: string
  file_id: string
  report_config: any
}

export interface ReportGenerationResponse {
  report_id: string
  status: string
  download_url?: string
}

export interface HealthCheckResponse {
  status: string
  timestamp: string
  version: string
  uptime: number
}

// Enums - 简化为纯对话
export enum DialogueState {
  INITIAL = "initial",
  ERROR = "error"
}

