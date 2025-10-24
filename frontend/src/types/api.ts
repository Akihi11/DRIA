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

