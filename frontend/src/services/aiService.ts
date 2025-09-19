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
   * 处理用户对话
   * @param userInput 用户输入
   * @param fileInfo 文件信息（如果有）
   * @param context 对话上下文
   */
  async processDialogue(
    userInput: string, 
    fileInfo?: any, 
    context?: any
  ): Promise<AIResponse> {
    
    // 检查是否请求配置信息
    const input = userInput.toLowerCase()
    if (input.includes('配置') || input.includes('设置') || input.includes('api')) {
      const configCheck = this.checkConfiguration()
      return {
        content: configCheck.message,
        suggestedActions: configCheck.configured 
          ? ['查看配置信息', '继续使用'] 
          : ['如何配置API', '使用模拟模式', '了解更多']
      }
    }
    
    // 如果配置了真实API，尝试使用真实API（目前暂未实现，仍使用mock）
    // if (this.isConfigured) {
    //   try {
    //     return await this.callRealAPI(userInput, fileInfo, context)
    //   } catch (error) {
    //     console.error('Real API failed, falling back to mock:', error)
    //   }
    // }
    
    // 使用模拟AI响应
    return this.mockAIResponse(userInput, fileInfo, context)
  }

  /**
   * 模拟AI响应 - 用于测试
   * 实际使用时替换为真实的API调用
   */
  private async mockAIResponse(
    userInput: string, 
    fileInfo?: any, 
    context?: any
  ): Promise<AIResponse> {
    
    // 模拟处理时间
    await new Promise(resolve => setTimeout(resolve, 1000))

    const input = userInput.toLowerCase()
    const hasFile = !!fileInfo

    // 根据用户输入和当前状态生成不同的响应
    
    // 文件上传后的响应
    if (input.includes('上传') && hasFile) {
      return {
        content: `文件上传成功！我已经检测到您的数据文件包含 ${fileInfo.available_channels?.length || 0} 个数据通道。\n\n请选择您需要生成的报表类型：`,
        suggestedActions: [
          '生成稳态分析报表',
          '生成功能计算报表', 
          '生成状态评估报表',
          '生成完整分析报表',
          '生成其他报表类型(.json)'
        ]
      }
    }

    // === 三大报表的配置流程 ===
    
    // 稳态分析报表配置
    if (input.includes('稳态') || input.includes('稳定')) {
      if (!context?.stableStateConfigured) {
        return {
          content: '好的，我将为您配置稳态分析报表。\n\n请指定用于判断稳定状态的主要通道（如：Ng(rpm)）：',
          suggestedActions: [
            '使用 Ng(rpm)',
            '使用 Temperature(°C)',
            '使用 Pressure(kPa)',
            '自定义通道'
          ]
        }
      } else {
        return {
          content: '稳态分析参数已配置完成：\n\n- 分析通道：' + (context.stableChannel || 'Ng(rpm)') + '\n- 稳定条件：平均值 > 15000\n- 时间窗口：1秒\n\n开始生成报表吗？',
          suggestedActions: [
            '确认生成',
            '修改配置',
            '取消'
          ]
        }
      }
    }

    // 功能计算报表配置
    if (input.includes('功能') || input.includes('计算')) {
      if (!context?.functionalConfigured) {
        return {
          content: '好的，我将为您配置功能计算报表。\n\n功能计算包括以下指标：\n- 时间基准\n- 启动时间\n- 点火时间\n- Ng余转时间\n\n请选择计算哪些指标：',
          suggestedActions: [
            '全部指标',
            '仅时间基准',
            '时间基准+启动时间',
            '自定义选择'
          ]
        }
      } else {
        return {
          content: '功能计算参数已配置完成。开始生成报表吗？',
          suggestedActions: [
            '确认生成',
            '修改配置',
            '取消'
          ]
        }
      }
    }

    // 状态评估报表配置
    if (input.includes('状态') || input.includes('评估')) {
      if (!context?.statusEvalConfigured) {
        return {
          content: '好的，我将为您配置状态评估报表。\n\n状态评估包括以下检测项：\n- 超温检测\n- Ng余转时间\n- 压力异常\n- 振动异常\n\n请选择需要评估的项目：',
          suggestedActions: [
            '全部项目',
            '仅超温检测',
            '超温+Ng余转',
            '自定义选择'
          ]
        }
      } else {
        return {
          content: '状态评估参数已配置完成。开始生成报表吗？',
          suggestedActions: [
            '确认生成',
            '修改配置',
            '取消'
          ]
        }
      }
    }

    // === 完整分析报表流程 ===
    if (input.includes('完整') || input.includes('全部')) {
      // 按顺序引导填写：稳态 -> 功能 -> 状态评估
      if (!context?.stableStateConfigured) {
        return {
          content: '很好！我将帮您生成包含所有三个部分的完整分析报表。\n\n让我们从稳态分析开始。请选择用于判断稳定状态的主要通道：',
          suggestedActions: [
            '使用 Ng(rpm)',
            '使用 Temperature(°C)',
            '使用 Pressure(kPa)',
            '自定义通道'
          ]
        }
      } else if (!context?.functionalConfigured) {
        return {
          content: '稳态分析配置完成！\n\n接下来配置功能计算部分。请选择需要计算的指标：',
          suggestedActions: [
            '全部指标',
            '仅时间基准',
            '时间基准+启动时间',
            '自定义选择'
          ]
        }
      } else if (!context?.statusEvalConfigured) {
        return {
          content: '功能计算配置完成！\n\n最后配置状态评估部分。请选择需要评估的项目：',
          suggestedActions: [
            '全部项目',
            '仅超温检测',
            '超温+Ng余转',
            '自定义选择'
          ]
        }
      } else {
        return {
          content: '完整分析报表的所有配置已完成！\n\n包括：\n✓ 稳态分析\n✓ 功能计算\n✓ 状态评估\n\n现在开始生成报表吗？',
          suggestedActions: [
            '确认生成完整报表',
            '查看配置摘要',
            '修改配置'
          ]
        }
      }
    }

    // === 其他报表类型（JSON配置）===
    if (input.includes('其他') || input.includes('json')) {
      return {
        content: '您选择了使用自定义JSON配置生成报表。\n\n请上传包含报表配置的 .json 文件：',
        suggestedActions: [
          '上传JSON配置文件',
          '返回选择其他报表'
        ]
      }
    }

    // === 确认生成 ===
    if (input.includes('确认') && input.includes('生成')) {
      return {
        content: '正在生成报表，请稍候...\n\n报表生成完成后，您可以下载Excel文件查看详细结果。',
        suggestedActions: [
          '查看报表列表',
          '生成其他类型报表'
        ],
        isComplete: true
      }
    }

    // === 帮助信息 ===
    if (input.includes('帮助') || input.includes('说明')) {
      return {
        content: '我可以帮您：\n\n1. 上传CSV/Excel数据文件\n2. 生成稳态分析报表\n3. 生成功能计算报表\n4. 生成状态评估报表\n5. 生成完整分析报表\n6. 使用JSON配置生成自定义报表\n\n请告诉我您需要什么帮助？',
        suggestedActions: [
          '上传数据文件'
        ]
      }
    }

    // === 示例数据 ===
    if (input.includes('示例') || input.includes('演示')) {
      return {
        content: '示例数据展示了典型的航空发动机测试数据格式。\n\n数据通常包含以下通道：\n- Ng(rpm): 燃气发生器转速\n- Temperature(°C): 温度\n- Pressure(kPa): 压力\n- Fuel_Flow(kg/h): 燃油流量\n- Vibration(mm/s): 振动\n\n您可以上传类似格式的数据文件开始分析。',
        suggestedActions: [
          '上传CSV文件',
          '上传Excel文件'
        ]
      }
    }

    // === 默认响应（无文件） ===
    if (!hasFile) {
      return {
        content: '您好！请先上传您的数据文件（CSV或Excel格式），我将帮助您生成专业的分析报表。',
        suggestedActions: [
          '上传CSV文件',
          '上传Excel文件'
        ]
      }
    }

    // === 默认响应（有文件）===
    return {
      content: '我理解您的需求。您已上传数据文件，现在可以选择生成以下类型的报表：',
      suggestedActions: [
        '生成稳态分析报表',
        '生成功能计算报表',
        '生成状态评估报表',
        '生成完整分析报表',
        '生成其他报表类型(.json)'
      ]
    }
  }

  /**
   * 真实的API调用方法 - 后续替换模拟方法
   */
  private async callRealAPI(
    userInput: string, 
    fileInfo?: any, 
    context?: any
  ): Promise<AIResponse> {
    
    try {
      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'gpt-3.5-turbo',
          messages: [
            {
              role: 'system',
              content: '你是一个专业的报表生成助手，帮助用户分析数据并生成报表。'
            },
            {
              role: 'user',
              content: userInput
            }
          ],
          max_tokens: 500,
          temperature: 0.7
        })
      })

      const data = await response.json()
      
      return {
        content: data.choices[0].message.content,
        suggestedActions: this.extractSuggestedActions(data.choices[0].message.content)
      }
    } catch (error) {
      console.error('AI API调用失败:', error)
      // 回退到模拟响应
      return this.mockAIResponse(userInput, fileInfo, context)
    }
  }

  /**
   * 从AI响应中提取建议操作
   */
  private extractSuggestedActions(content: string): string[] {
    // 简单的关键词匹配，实际可以更智能
    const actions = []
    
    if (content.includes('上传') || content.includes('文件')) {
      actions.push('上传数据文件')
    }
    if (content.includes('稳态') || content.includes('稳定')) {
      actions.push('生成稳态分析报表')
    }
    if (content.includes('功能') || content.includes('计算')) {
      actions.push('生成功能计算报表')
    }
    if (content.includes('状态') || content.includes('评估')) {
      actions.push('生成状态评估报表')
    }
    if (content.includes('帮助') || content.includes('说明')) {
      actions.push('查看帮助')
    }

    return actions.length > 0 ? actions : ['继续对话', '查看帮助']
  }
}

// 创建单例实例
export const aiService = new AIService()
export default aiService
