/**
 * AI对话服务 - 使用外部API
 * 后续可以替换为本地模型
 */

export interface AIResponse {
  content: string
  suggestedActions?: string[]
  isComplete?: boolean
}

export class AIService {
  private apiKey: string
  private baseUrl: string
  private isConfigured: boolean

  constructor() {
    // 使用免费的AI API，后续可以替换为本地模型
    this.apiKey = localStorage.getItem('dria_ai_api_key') || '' 
    this.baseUrl = localStorage.getItem('dria_ai_base_url') || 'https://api.openai.com/v1'
    this.isConfigured = !!this.apiKey && this.apiKey !== 'your-api-key-here'
  }

  /**
   * 检查大模型是否已配置
   */
  checkConfiguration(): { configured: boolean; message: string } {
    if (!this.isConfigured || !this.apiKey) {
      return {
        configured: false,
        message: '大模型未配置。当前使用模拟对话模式。\n\n如需使用真实AI对话功能，请在设置中添加API配置。'
      }
    }
    return {
      configured: true,
      message: '大模型已配置'
    }
  }

  /**
   * 更新AI配置
   */
  updateConfiguration(apiKey: string, baseUrl?: string) {
    this.apiKey = apiKey
    if (baseUrl) {
      this.baseUrl = baseUrl
    }
    this.isConfigured = !!apiKey && apiKey !== 'your-api-key-here'
    
    // 保存到 localStorage
    localStorage.setItem('dria_ai_api_key', apiKey)
    if (baseUrl) {
      localStorage.setItem('dria_ai_base_url', baseUrl)
    }
  }

  /**
   * 处理用户对话 - 纯对话实现
   * @param userInput 用户输入
   * @param fileInfo 文件信息（已移除，纯对话不需要）
   * @param context 对话上下文
   */
  async processDialogue(
    userInput: string, 
    fileInfo?: any, 
    context?: any
  ): Promise<AIResponse> {
    
    try {
      // 直接调用后端对话API
      const response = await fetch('/api/ai_report/dialogue', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: context?.sessionId || 'default-session',
          user_input: userInput,
          dialogue_state: context?.currentState || 'INITIAL'
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      
      return {
        content: data.ai_response,
        suggestedActions: data.suggested_actions || [],
        isComplete: data.is_complete || false
      }
    } catch (error) {
      console.error('Backend API call failed:', error)
      // 回退到简单的错误响应
      return {
        content: '抱歉，AI服务暂时不可用。请稍后再试。',
        suggestedActions: ['重试', '查看帮助']
      }
    }
  }

  /**
   * 模拟AI响应 - 纯对话实现
   */
  private async mockAIResponse(
    userInput: string, 
    fileInfo?: any, 
    context?: any
  ): Promise<AIResponse> {
    
    // 模拟处理时间
    await new Promise(resolve => setTimeout(resolve, 1000))

    const input = userInput.toLowerCase()

    // 简单的纯对话响应
    if (input.includes('你好') || input.includes('hello') || input.includes('hi')) {
      return {
        content: '你好！我是AI助手，很高兴为您服务。请告诉我您需要什么帮助？',
        suggestedActions: ['继续对话', '查看帮助']
      }
    }

    if (input.includes('你是谁') || input.includes('介绍') || input.includes('什么')) {
      return {
        content: '我是AI助手，可以帮助您解答问题、提供建议和支持。',
        suggestedActions: ['继续对话', '查看帮助']
      }
    }

    if (input.includes('帮助') || input.includes('说明')) {
      return {
        content: '我可以帮助您解答各种问题，提供专业建议和支持。请告诉我您需要什么帮助？',
        suggestedActions: ['继续对话', '重新开始']
      }
    }

    // 默认响应
    return {
      content: `我理解您的输入：${userInput}。请告诉我您需要什么帮助？`,
      suggestedActions: ['继续对话', '查看帮助']
    }
  }

}

// 创建单例实例
export const aiService = new AIService()
export default aiService
