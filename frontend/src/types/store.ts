import { DialogueState, FileInfo as ApiFileInfo, ReportConfig } from './api'

// Re-export FileInfo for convenience
export type FileInfo = ApiFileInfo

// Store State Types
export interface AppState {
  ui: UIState
  dialogue: DialogueState
  file: FileState
  reports: ReportsState
}

export interface UIState {
  loading: boolean
  error: string | null
  currentPage: string
  sidebarCollapsed: boolean
}

export interface DialogueStoreState {
  sessionId: string | null
  messages: Message[]
  currentState: DialogueState
  isLoading: boolean
  error: string | null
}

export interface FileState {
  currentFile: FileInfo | null
  uploadProgress: number
  isUploading: boolean
  error: string | null
}

export interface ReportsState {
  reports: ReportItem[]
  currentReport: ReportItem | null
  isGenerating: boolean
  error: string | null
}

// Message Types
export interface Message {
  id: string
  type: 'user' | 'ai' | 'system'
  content: string
  timestamp: Date
  metadata?: MessageMetadata
}

export interface MessageMetadata {
  fileInfo?: FileInfo
  suggestedActions?: string[]
  reportConfig?: ReportConfig
  reportId?: string
  channelStats?: any // Channel statistics data
}

// Report Types
export interface ReportItem {
  id: string
  name: string
  fileId: string
  fileName: string
  generatedAt: Date
  filePath: string
  config: ReportConfig
  status: 'generating' | 'completed' | 'failed'
  error?: string
}

// Action Types
export interface Action {
  type: string
  payload?: any
}

// Store Actions
export interface UIActions {
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setCurrentPage: (page: string) => void
  toggleSidebar: () => void
}

export interface DialogueActions {
  initSession: () => void
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setState: (state: DialogueState) => void
  clearSession: () => void
}

export interface FileActions {
  setCurrentFile: (file: FileInfo | null) => void
  setUploadProgress: (progress: number) => void
  setUploading: (uploading: boolean) => void
  setError: (error: string | null) => void
}

export interface ReportsActions {
  addReport: (report: ReportItem) => void
  updateReport: (id: string, updates: Partial<ReportItem>) => void
  setCurrentReport: (report: ReportItem | null) => void
  setGenerating: (generating: boolean) => void
  setError: (error: string | null) => void
  deleteReport: (id: string) => void
}
