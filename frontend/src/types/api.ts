// API Request/Response Types
export interface FileUploadRequest {
  file: File
}

export interface FileUploadResponse {
  file_id: string
  filename: string
  size: number
  upload_time: string
  available_channels: string[]
}

export interface DialogueRequest {
  session_id: string
  user_input: string
  file_id?: string
  context?: Record<string, any>
}

export interface DialogueResponse {
  session_id: string
  ai_response: string
  dialogue_state: DialogueState
  suggested_actions?: string[]
  file_info?: FileInfo
  is_complete: boolean
  error_message?: string
}

export interface ReportGenerationRequest {
  session_id: string
  file_id: string
  config: Record<string, any>
  report_type?: string
}

export interface ReportGenerationResponse {
  report_id: string
  session_id: string
  report_url: string  // Changed from file_path to match backend
  generation_time: string
  file_size: number  // Added to match backend
  success: boolean
  error_message?: string
}

export interface HealthCheckResponse {
  status: string
  timestamp: string
  version: string
  uptime: number
}

// Enums
export enum DialogueState {
  INITIAL = "initial",
  FILE_UPLOADED = "file_uploaded", 
  CONFIGURING = "configuring",
  GENERATING = "generating",
  COMPLETED = "completed",
  ERROR = "error"
}

// Data Models
export interface FileInfo {
  file_id: string
  filename: string
  file_size: number  // 与后端字段名保持一致
  upload_time: string
  available_channels: string[]
}

export interface ChannelData {
  channel_name: string
  unit: string
  data_points: DataPoint[]
  sample_rate: number
}

export interface DataPoint {
  timestamp: number
  value: number
}

export interface ReportSection {
  section_type: string
  title: string
  content: Record<string, any>
  charts?: ChartData[]
}

export interface ChartData {
  chart_type: string
  title: string
  data: Record<string, any>
}

// Configuration Models
export interface ReportConfig {
  sourceFileId: string
  reportConfig: {
    sections: string[]
    stableState?: StableStateConfig
    functionalCalc?: FunctionalCalcConfig
    statusEval?: StatusEvalConfig
  }
}

export interface StableStateConfig {
  displayChannels: string[]
  conditionLogic: "AND" | "OR"
  conditions: ConditionConfig[]
  condition?: ConditionConfig  // Backward compatibility
}

export interface ConditionConfig {
  type: "statistic" | "amplitude_change"
  channel: string
  statistic?: string
  duration: number
  logic: string
  threshold: number
}

export interface FunctionalCalcConfig {
  time_base?: TimeBaseConfig
  startup_time?: StartupTimeConfig
  ignition_time?: IgnitionTimeConfig
  rundown_ng?: RundownNgConfig
  rundown_np?: RundownNpConfig
}

export interface TimeBaseConfig {
  channel: string
  statistic: string
  duration: number
  logic: string
  threshold: number
}

export interface StartupTimeConfig {
  channel: string
  statistic: string
  duration: number
  logic: string
  threshold: number
}

export interface IgnitionTimeConfig {
  channel: string
  type: string
  duration: number
  logic: "突变>" | "突变<"
  threshold: number
}

export interface RundownNgConfig {
  channel: string
  statistic: string
  duration: number
  threshold1: number
  threshold2: number
}

export interface RundownNpConfig {
  channel: string
  statistic?: string
  duration: number
  threshold1: number
  threshold2: number
}

export interface StatusEvalConfig {
  evaluations: EvaluationConfig[]
}

export interface EvaluationConfig {
  item: string
  type: "continuous_check" | "event_check"
  conditionLogic?: "AND" | "OR"
  conditions?: StatusCondition[]
  condition?: StatusCondition  // For single condition or backward compatibility
  logic?: string
  threshold?: number
  expected?: string
}

export interface StatusCondition {
  channel: string
  statistic?: string
  type?: string
  duration?: number
  logic: string
  threshold: number
  source?: string
  expected?: string
}
