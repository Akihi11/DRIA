// API endpoints
export const API_ENDPOINTS = {
  HEALTH: '/health',
  FILE_UPLOAD: '/upload',
  DIALOGUE: '/ai_report/dialogue',
  REPORT_GENERATE: '/reports/generate',
  REPORT_DOWNLOAD: '/reports/download',
  FILE_INFO: '/ai_report/file',
} as const

// File upload constraints
export const FILE_CONSTRAINTS = {
  MAX_SIZE: 50 * 1024 * 1024, // 50MB
  ALLOWED_TYPES: ['csv', 'xlsx', 'xls'],
  MIME_TYPES: [
    'text/csv',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
  ],
} as const

// Dialogue states
export const DIALOGUE_STATES = {
  INITIAL: 'initial',
  FILE_UPLOADED: 'file_uploaded',
  CONFIGURING: 'configuring',
  GENERATING: 'generating',
  COMPLETED: 'completed',
  ERROR: 'error',
} as const

// Report sections
export const REPORT_SECTIONS = {
  STABLE_STATE: 'stableState',
  FUNCTIONAL_CALC: 'functionalCalc',
  STATUS_EVAL: 'statusEval',
} as const

// Report section labels
export const REPORT_SECTION_LABELS = {
  [REPORT_SECTIONS.STABLE_STATE]: '稳态分析',
  [REPORT_SECTIONS.FUNCTIONAL_CALC]: '功能计算',
  [REPORT_SECTIONS.STATUS_EVAL]: '状态评估',
} as const

// Message types
export const MESSAGE_TYPES = {
  USER: 'user',
  AI: 'ai',
  SYSTEM: 'system',
} as const

// Report status
export const REPORT_STATUS = {
  GENERATING: 'generating',
  COMPLETED: 'completed',
  FAILED: 'failed',
} as const

// Report status labels
export const REPORT_STATUS_LABELS = {
  [REPORT_STATUS.GENERATING]: '生成中',
  [REPORT_STATUS.COMPLETED]: '已完成',
  [REPORT_STATUS.FAILED]: '生成失败',
} as const

// Navigation routes
export const ROUTES = {
  HOME: '/',
  CHAT: '/chat',
  REPORTS: '/reports',
} as const

// Local storage keys
export const STORAGE_KEYS = {
  SESSION_ID: 'dria_session_id',
  USER_PREFERENCES: 'dria_user_preferences',
  CHAT_HISTORY: 'dria_chat_history',
  LAST_FILE: 'dria_last_file',
} as const

// Theme colors
export const THEME_COLORS = {
  PRIMARY: '#1890ff',
  SUCCESS: '#52c41a',
  WARNING: '#faad14',
  ERROR: '#f5222d',
  INFO: '#1890ff',
  TEXT_PRIMARY: '#262626',
  TEXT_SECONDARY: '#8c8c8c',
  BORDER: '#d9d9d9',
  BACKGROUND: '#fafafa',
} as const

// Chart colors
export const CHART_COLORS = [
  '#1890ff',
  '#52c41a',
  '#faad14',
  '#f5222d',
  '#722ed1',
  '#fa541c',
  '#13c2c2',
  '#eb2f96',
  '#ffc53d',
  '#40a9ff',
] as const

// Analysis types
export const ANALYSIS_TYPES = {
  STABLE_STATE: 'stable_state',
  FUNCTIONAL_CALC: 'functional_calc',
  STATUS_EVAL: 'status_eval',
} as const

// Condition types
export const CONDITION_TYPES = {
  STATISTIC: 'statistic',
  AMPLITUDE_CHANGE: 'amplitude_change',
  DIFFERENCE: 'difference',
} as const

// Logic operators
export const LOGIC_OPERATORS = {
  GREATER_THAN: '>',
  LESS_THAN: '<',
  GREATER_EQUAL: '>=',
  LESS_EQUAL: '<=',
  EQUAL: '=',
  NOT_EQUAL: '!=',
  SUDDEN_INCREASE: '突变>',
  SUDDEN_DECREASE: '突变<',
} as const

// Statistics types
export const STATISTICS_TYPES = {
  AVERAGE: '平均值',
  MAXIMUM: '最大值',
  MINIMUM: '最小值',
  INSTANT: '瞬时值',
  STANDARD_DEVIATION: '标准差',
  RANGE: '极差',
} as const

// Evaluation types
export const EVALUATION_TYPES = {
  CONTINUOUS_CHECK: 'continuous_check',
  EVENT_CHECK: 'event_check',
} as const

// Expected results
export const EXPECTED_RESULTS = {
  NEVER_HAPPEN: 'never_happen',
  ALWAYS_HAPPEN: 'always_happen',
  SOMETIMES_HAPPEN: 'sometimes_happen',
} as const

// Time units
export const TIME_UNITS = {
  SECONDS: 's',
  MILLISECONDS: 'ms',
  MINUTES: 'min',
  HOURS: 'h',
} as const

// Default values
export const DEFAULTS = {
  PAGE_SIZE: 10,
  DEBOUNCE_DELAY: 300,
  THROTTLE_DELAY: 1000,
  REQUEST_TIMEOUT: 300000,
  UPLOAD_TIMEOUT: 300000,
  MAX_MESSAGE_LENGTH: 1000,
  MAX_FILE_NAME_LENGTH: 100,
} as const

// Error messages
export const ERROR_MESSAGES = {
  NETWORK_ERROR: '网络连接错误，请检查网络连接',
  FILE_TOO_LARGE: '文件大小超过限制',
  INVALID_FILE_TYPE: '不支持的文件类型',
  UPLOAD_FAILED: '文件上传失败',
  DOWNLOAD_FAILED: '文件下载失败',
  GENERATE_FAILED: '报表生成失败',
  DIALOGUE_FAILED: '对话处理失败',
  SESSION_EXPIRED: '会话已过期，请重新开始',
  UNKNOWN_ERROR: '发生未知错误',
} as const

// Success messages
export const SUCCESS_MESSAGES = {
  FILE_UPLOADED: '文件上传成功',
  REPORT_GENERATED: '报表生成成功',
  REPORT_DOWNLOADED: '报表下载成功',
  SESSION_STARTED: '会话已开始',
  MESSAGE_SENT: '消息发送成功',
} as const

// Validation rules
export const VALIDATION = {
  FILE_SIZE_MIN: 1024, // 1KB
  FILE_SIZE_MAX: FILE_CONSTRAINTS.MAX_SIZE,
  MESSAGE_LENGTH_MIN: 1,
  MESSAGE_LENGTH_MAX: DEFAULTS.MAX_MESSAGE_LENGTH,
  SESSION_ID_LENGTH: 36, // UUID length
} as const

// Animation durations (in milliseconds)
export const ANIMATIONS = {
  FAST: 200,
  NORMAL: 300,
  SLOW: 500,
  FADE_IN: 300,
  SLIDE_IN: 250,
} as const
