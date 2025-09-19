import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import { v4 as uuidv4 } from 'uuid'
import { 
  Message, 
  FileInfo, 
  ReportItem,
  UIState,
  DialogueStoreState,
  FileState,
  ReportsState
} from '../types/store'
import { DialogueState } from '../types/api'

// UI Store
interface UIStore extends UIState {
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setCurrentPage: (page: string) => void
  toggleSidebar: () => void
}

export const useUIStore = create<UIStore>()(
  subscribeWithSelector((set) => ({
    loading: false,
    error: null,
    currentPage: '/',
    sidebarCollapsed: false,
    
    setLoading: (loading) => set({ loading }),
    setError: (error) => set({ error }),
    setCurrentPage: (page) => set({ currentPage: page }),
    toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  }))
)

// Dialogue Store
interface DialogueStore extends DialogueStoreState {
  initSession: () => void
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setState: (state: DialogueState) => void
  clearSession: () => void
  updateLastMessage: (updates: Partial<Message>) => void
}

export const useDialogueStore = create<DialogueStore>()(
  subscribeWithSelector((set, get) => ({
    sessionId: null,
    messages: [],
    currentState: DialogueState.INITIAL,
    isLoading: false,
    error: null,
    
    initSession: () => {
      const sessionId = uuidv4()
      set({ 
        sessionId,
        messages: [],
        currentState: DialogueState.INITIAL,
        error: null
      })
    },
    
    addMessage: (messageData) => {
      const message: Message = {
        ...messageData,
        id: uuidv4(),
        timestamp: new Date()
      }
      set((state) => ({
        messages: [...state.messages, message]
      }))
    },
    
    updateLastMessage: (updates) => {
      set((state) => ({
        messages: state.messages.map((msg, index) => 
          index === state.messages.length - 1 
            ? { ...msg, ...updates }
            : msg
        )
      }))
    },
    
    setLoading: (isLoading) => set({ isLoading }),
    setError: (error) => set({ error }),
    setState: (currentState) => set({ currentState }),
    
    clearSession: () => set({
      sessionId: null,
      messages: [],
      currentState: DialogueState.INITIAL,
      isLoading: false,
      error: null
    }),
  }))
)

// File Store
interface FileStore extends FileState {
  setCurrentFile: (file: FileInfo | null) => void
  setUploadProgress: (progress: number) => void
  setUploading: (uploading: boolean) => void
  setError: (error: string | null) => void
  clearFile: () => void
}

export const useFileStore = create<FileStore>()(
  subscribeWithSelector((set) => ({
    currentFile: null,
    uploadProgress: 0,
    isUploading: false,
    error: null,
    
    setCurrentFile: (currentFile) => set({ currentFile }),
    setUploadProgress: (uploadProgress) => set({ uploadProgress }),
    setUploading: (isUploading) => set({ isUploading }),
    setError: (error) => set({ error }),
    
    clearFile: () => set({
      currentFile: null,
      uploadProgress: 0,
      isUploading: false,
      error: null
    }),
  }))
)

// Reports Store
interface ReportsStore extends ReportsState {
  addReport: (report: ReportItem) => void
  updateReport: (id: string, updates: Partial<ReportItem>) => void
  setCurrentReport: (report: ReportItem | null) => void
  setGenerating: (generating: boolean) => void
  setError: (error: string | null) => void
  deleteReport: (id: string) => void
  loadReports: () => Promise<void>
}

export const useReportsStore = create<ReportsStore>()(
  subscribeWithSelector((set, get) => ({
    reports: [],
    currentReport: null,
    isGenerating: false,
    error: null,
    
    addReport: (report) => set((state) => ({
      reports: [report, ...state.reports]
    })),
    
    updateReport: (id, updates) => set((state) => ({
      reports: state.reports.map(report => 
        report.id === id ? { ...report, ...updates } : report
      )
    })),
    
    setCurrentReport: (currentReport) => set({ currentReport }),
    setGenerating: (isGenerating) => set({ isGenerating }),
    setError: (error) => set({ error }),
    
    deleteReport: (id) => set((state) => ({
      reports: state.reports.filter(report => report.id !== id)
    })),
    
    loadReports: async () => {
      try {
        // This would call the API to load reports
        // For now, we'll use the existing reports
        console.log('Loading reports from API...')
      } catch (error) {
        set({ error: 'Failed to load reports' })
      }
    },
  }))
)

// Combined store hook for convenience
export const useAppStore = () => ({
  ui: useUIStore(),
  dialogue: useDialogueStore(),
  file: useFileStore(),
  reports: useReportsStore(),
})

// Selectors for commonly used state combinations
export const useIsAppLoading = () => {
  const uiLoading = useUIStore((state) => state.loading)
  const dialogueLoading = useDialogueStore((state) => state.isLoading)
  const fileUploading = useFileStore((state) => state.isUploading)
  const reportsGenerating = useReportsStore((state) => state.isGenerating)
  
  return uiLoading || dialogueLoading || fileUploading || reportsGenerating
}

export const useHasErrors = () => {
  const uiError = useUIStore((state) => state.error)
  const dialogueError = useDialogueStore((state) => state.error)
  const fileError = useFileStore((state) => state.error)
  const reportsError = useReportsStore((state) => state.error)
  
  return !!(uiError || dialogueError || fileError || reportsError)
}
