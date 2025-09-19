// Enhanced Error Handling Utilities
import { message } from 'antd'

export interface ErrorInfo {
  type: 'network' | 'api' | 'file' | 'validation' | 'unknown'
  code?: string | number
  message: string
  details?: any
}

export class ErrorHandler {
  /**
   * 处理并显示错误
   */
  static handle(error: any, context?: string): ErrorInfo {
    const errorInfo = this.parseError(error)
    this.showUserFriendlyMessage(errorInfo, context)
    this.logError(errorInfo, context)
    return errorInfo
  }

  /**
   * 解析错误类型和信息
   */
  static parseError(error: any): ErrorInfo {
    // 网络错误
    if (error.code === 'ECONNREFUSED' || error.code === 'NETWORK_ERROR') {
      return {
        type: 'network',
        code: error.code,
        message: '网络连接失败，请检查网络连接或稍后重试',
        details: error
      }
    }

    // 请求超时
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      return {
        type: 'network',
        code: 'TIMEOUT',
        message: '请求超时，请稍后重试',
        details: error
      }
    }

    // HTTP错误
    if (error.response) {
      const status = error.response.status
      const data = error.response.data

      switch (status) {
        case 400:
          return {
            type: 'api',
            code: status,
            message: data?.message || '请求参数错误，请检查输入信息',
            details: data
          }
        case 401:
          return {
            type: 'api',
            code: status,
            message: '认证失败，请重新登录',
            details: data
          }
        case 403:
          return {
            type: 'api',
            code: status,
            message: '权限不足，无法执行此操作',
            details: data
          }
        case 404:
          return {
            type: 'api',
            code: status,
            message: '请求的资源不存在',
            details: data
          }
        case 413:
          return {
            type: 'file',
            code: status,
            message: '文件太大，请选择较小的文件',
            details: data
          }
        case 422:
          return {
            type: 'validation',
            code: status,
            message: data?.message || '数据验证失败，请检查输入格式',
            details: data
          }
        case 429:
          return {
            type: 'api',
            code: status,
            message: '请求过于频繁，请稍后重试',
            details: data
          }
        case 500:
          return {
            type: 'api',
            code: status,
            message: '服务器内部错误，请联系管理员',
            details: data
          }
        case 502:
        case 503:
        case 504:
          return {
            type: 'api',
            code: status,
            message: '服务暂时不可用，请稍后重试',
            details: data
          }
        default:
          return {
            type: 'api',
            code: status,
            message: data?.message || `服务器错误 (${status})`,
            details: data
          }
      }
    }

    // 文件相关错误
    if (error.name === 'FileError' || error.message?.includes('file')) {
      return {
        type: 'file',
        message: '文件处理失败，请检查文件格式和大小',
        details: error
      }
    }

    // 验证错误
    if (error.name === 'ValidationError') {
      return {
        type: 'validation',
        message: error.message || '输入数据格式不正确',
        details: error
      }
    }

    // 默认错误
    return {
      type: 'unknown',
      message: error.message || '发生未知错误，请稍后重试',
      details: error
    }
  }

  /**
   * 显示用户友好的错误消息
   */
  static showUserFriendlyMessage(errorInfo: ErrorInfo, context?: string) {
    const contextPrefix = context ? `${context}: ` : ''
    
    switch (errorInfo.type) {
      case 'network':
        message.error({
          content: `${contextPrefix}${errorInfo.message}`,
          duration: 6,
          key: 'network-error'
        })
        break
      
      case 'file':
        message.error({
          content: `${contextPrefix}${errorInfo.message}`,
          duration: 5,
          key: 'file-error'
        })
        break
      
      case 'validation':
        message.warning({
          content: `${contextPrefix}${errorInfo.message}`,
          duration: 4,
          key: 'validation-error'
        })
        break
      
      case 'api':
        if (errorInfo.code === 500) {
          message.error({
            content: `${contextPrefix}${errorInfo.message}`,
            duration: 8,
            key: 'server-error'
          })
        } else {
          message.error({
            content: `${contextPrefix}${errorInfo.message}`,
            duration: 5,
            key: 'api-error'
          })
        }
        break
      
      default:
        message.error({
          content: `${contextPrefix}${errorInfo.message}`,
          duration: 4,
          key: 'unknown-error'
        })
    }
  }

  /**
   * 记录错误日志
   */
  static logError(errorInfo: ErrorInfo, context?: string) {
    const logData = {
      timestamp: new Date().toISOString(),
      context: context || 'unknown',
      type: errorInfo.type,
      code: errorInfo.code,
      message: errorInfo.message,
      details: errorInfo.details,
      userAgent: navigator.userAgent,
      url: window.location.href
    }

    // 开发环境下打印到控制台
    if (process.env.NODE_ENV === 'development') {
      console.group(`🚨 Error [${errorInfo.type.toUpperCase()}]`)
      console.error('Context:', context)
      console.error('Message:', errorInfo.message)
      console.error('Details:', errorInfo.details)
      console.groupEnd()
    }

    // 生产环境下可以发送到错误监控服务
    if (process.env.NODE_ENV === 'production') {
      // TODO: 发送到错误监控服务 (如 Sentry, LogRocket 等)
      // sendToErrorService(logData)
    }
  }

  /**
   * 创建重试函数
   */
  static createRetryHandler(
    originalFunction: Function,
    maxRetries: number = 3,
    delay: number = 1000
  ) {
    return async (...args: any[]) => {
      let lastError: any
      
      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
          return await originalFunction(...args)
        } catch (error) {
          lastError = error
          
          if (attempt === maxRetries) {
            throw lastError
          }
          
          // 检查是否应该重试
          if (!this.shouldRetry(error)) {
            throw lastError
          }
          
          // 延迟后重试
          await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, attempt)))
        }
      }
    }
  }

  /**
   * 判断是否应该重试
   */
  static shouldRetry(error: any): boolean {
    // 网络错误可以重试
    if (error.code === 'ECONNREFUSED' || error.code === 'NETWORK_ERROR') {
      return true
    }
    
    // 超时可以重试
    if (error.code === 'ECONNABORTED') {
      return true
    }
    
    // 服务器错误可以重试
    if (error.response?.status >= 500) {
      return true
    }
    
    // 429 (Too Many Requests) 可以重试
    if (error.response?.status === 429) {
      return true
    }
    
    return false
  }

  /**
   * 文件验证
   */
  static validateFile(file: File): { valid: boolean; error?: string } {
    const maxSize = 50 * 1024 * 1024 // 50MB
    const allowedTypes = ['text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
    
    if (file.size > maxSize) {
      return {
        valid: false,
        error: `文件大小超过限制 (${(maxSize / 1024 / 1024).toFixed(0)}MB)`
      }
    }
    
    if (!allowedTypes.includes(file.type) && !file.name.match(/\.(csv|xlsx?)$/i)) {
      return {
        valid: false,
        error: '不支持的文件格式，请上传 CSV 或 Excel 文件'
      }
    }
    
    return { valid: true }
  }

  /**
   * 创建全局错误处理器
   */
  static setupGlobalHandlers() {
    // 处理未捕获的Promise错误
    window.addEventListener('unhandledrejection', (event) => {
      console.error('Unhandled promise rejection:', event.reason)
      this.handle(event.reason, 'Unhandled Promise')
      event.preventDefault()
    })

    // 处理全局错误
    window.addEventListener('error', (event) => {
      console.error('Global error:', event.error)
      this.handle(event.error, 'Global Error')
    })
  }
}

// 导出便捷函数
export const handleError = ErrorHandler.handle.bind(ErrorHandler)
export const validateFile = ErrorHandler.validateFile.bind(ErrorHandler)
export const createRetryHandler = ErrorHandler.createRetryHandler.bind(ErrorHandler)

// 自动设置全局错误处理器
if (typeof window !== 'undefined') {
  ErrorHandler.setupGlobalHandlers()
}
