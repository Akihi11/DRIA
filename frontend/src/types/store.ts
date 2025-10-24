import { DialogueState } from './api'

// Store State Types
export interface AppState {
  ui: UIState
  dialogue: DialogueState
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

// Message Types
export interface Message {
  id: string
  type: 'user' | 'ai' | 'system'
  content: string
  timestamp: Date
  metadata?: MessageMetadata
}

export interface MessageMetadata {
  suggestedActions?: string[]
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

