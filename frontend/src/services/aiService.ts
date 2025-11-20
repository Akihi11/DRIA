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
  private isConfigured: boolean

  constructor() {
    // 使用免费的AI API，后续可以替换为本地模型
    this.apiKey = localStorage.getItem('dria_ai_api_key') || '' 
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
   * @param context 对话上下文
   */
  async processDialogue(
    userInput: string, 
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
        content: '抱歉，AI服务暂时不可用。请查看配置是否正确。',
        suggestedActions: []
      }
    }
  }


}

// 创建单例实例
export const aiService = new AIService()
export default aiService
