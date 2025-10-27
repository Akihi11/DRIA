import React, { useState, useEffect, useRef } from 'react'
import { message } from 'antd'
import ChatContainer, { ChatContainerRef } from '../components/Chat/ChatContainer'
import ConfigStatusBar from '../components/ConfigStatusBar'
import { Message } from '../types/store'
import { DialogueState } from '../types/api'
import aiService from '../services/aiService'
import apiService from '../services/api'
import { v4 as uuidv4 } from 'uuid'

const ChatPage: React.FC = () => {
  const [sessionId, setSessionId] = useState<string>('')
  const [messages, setMessages] = useState<Message[]>([])
  const [currentState] = useState<DialogueState>(DialogueState.INITIAL)
  const [isLoading, setIsLoading] = useState(false)
  const [, setError] = useState<string | null>(null)
  const [configMode, setConfigMode] = useState<{
    isActive: boolean
    sessionId: string
    currentState: string
    reportType: string
    currentParams: any
  }>({
    isActive: false,
    sessionId: '',
    currentState: '',
    reportType: '',
    currentParams: {}
  })
  const chatContainerRef = useRef<ChatContainerRef>(null)

  // Initialize session on component mount
  useEffect(() => {
    const newSessionId = uuidv4()
    setSessionId(newSessionId)
    
    // 添加欢迎消息
    const welcomeMessage: Message = {
      id: uuidv4(),
      type: 'ai',
      content: '您好！我是AI助手，可以帮助您分析数据并生成报表。请先上传您的数据文件（支持CSV、Excel格式），然后告诉我您的分析需求。',
      timestamp: new Date()
    }
    setMessages([welcomeMessage])
  }, [])

  // 检查配置状态
  const checkConfigStatus = async () => {
    if (!sessionId) return
    
    try {
      const status = await apiService.getConfigStatus(sessionId)
      if (status && status.state !== 'initial' && status.state !== 'completed') {
        setConfigMode({
          isActive: true,
          sessionId: sessionId,
          currentState: status.state,
          reportType: status.report_type || '未知',
          currentParams: status.current_params || {}
        })
      } else {
        // 如果不是活跃配置状态，清空配置模式
        if (configMode.isActive) {
          setConfigMode({
            isActive: false,
            sessionId: '',
            currentState: '',
            reportType: '',
            currentParams: {}
          })
        }
      }
    } catch (error) {
      // 如果是404错误，说明没有配置会话，确保配置模式关闭
      if ((error as any).response?.status === 404) {
        if (configMode.isActive) {
          setConfigMode({
            isActive: false,
            sessionId: '',
            currentState: '',
            reportType: '',
            currentParams: {}
          })
        }
      } else {
        // 其他错误只记录日志，不影响正常对话
        console.log('Config status check failed:', error)
      }
    }
  }

  // 完成配置
  const handleCompleteConfig = async () => {
    if (!configMode.sessionId) return

    setIsLoading(true)
    
    try {
      // 调用完成配置API
      const response = await fetch('/api/config-dialogue/complete-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: configMode.sessionId
        })
      })
      
      const data = await response.json()
      
      if (!response.ok) {
        throw new Error(data.detail || '完成配置失败')
      }
      
      // 添加响应消息
      const aiMessage: Message = {
        id: uuidv4(),
        type: 'ai',
        content: data.message,
        timestamp: new Date(),
        metadata: {
          configState: data.status,
          currentParams: data.config
        }
      }
      
      setMessages(prev => [...prev, aiMessage])
      
      // 更新配置状态
      setConfigMode(prev => ({
        ...prev,
        currentState: data.status,
        currentParams: data.config || prev.currentParams
      }))
      
      // 如果配置完成，退出配置模式
      if (data.status === 'completed') {
        setConfigMode({
          isActive: false,
          sessionId: '',
          currentState: '',
          reportType: '',
          currentParams: {}
        })
      }
      
    } catch (error) {
      console.error('Complete config error:', error)
      const errorMessage = '完成配置时出现错误，请稍后重试。'
      
      const aiErrorMessage: Message = {
        id: uuidv4(),
        type: 'ai',
        content: errorMessage,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, aiErrorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  // 取消配置
  const handleCancelConfig = async () => {
    if (!configMode.sessionId) return

    setIsLoading(true)
    
    try {
      // 调用专门的取消配置API
      const response = await fetch('/api/config-dialogue/cancel-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: configMode.sessionId
        })
      })
      
      const data = await response.json()
      
      if (!response.ok) {
        throw new Error(data.detail || '取消配置失败')
      }
      
      // 退出配置模式
      setConfigMode({
        isActive: false,
        sessionId: '',
        currentState: '',
        reportType: '',
        currentParams: {}
      })
      
      // 添加取消消息
      const cancelMessage: Message = {
        id: uuidv4(),
        type: 'ai',
        content: '配置已取消，回到对话模式。您可以继续与我聊天，或者重新开始配置报表。',
        timestamp: new Date(),
        metadata: {
          suggestedActions: ['稳态分析', '功能计算', '状态评估', '完整报表']
        }
      }
      
      setMessages(prev => [...prev, cancelMessage])
      
    } catch (error) {
      console.error('Cancel config error:', error)
      // 即使API调用失败，也要退出配置模式
      setConfigMode({
        isActive: false,
        sessionId: '',
        currentState: '',
        reportType: '',
        currentParams: {}
      })
      
      // 显示错误消息
      const errorMessage: Message = {
        id: uuidv4(),
        type: 'ai',
        content: '配置已取消，回到对话模式。您可以继续与我聊天，或者重新开始配置报表。',
        timestamp: new Date(),
        metadata: {
          suggestedActions: ['稳态分析', '功能计算', '状态评估', '完整报表']
        }
      }
      
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSendMessage = async (content: string) => {
    if (!sessionId || isLoading) return

    // Add user message
    const userMessage: Message = {
      id: uuidv4(),
      type: 'user',
      content,
      timestamp: new Date()
    }
    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    setError(null)

    try {
      // 检查是否在配置模式
      if (configMode.isActive && configMode.sessionId) {
        // 配置模式：使用配置对话API
        const response = await fetch('/api/config-dialogue/update-config', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            session_id: configMode.sessionId,
            user_input: content
          })
        })
        
        const configResponse = await response.json()
        
        if (configResponse.success) {
          // 配置更新成功
          const aiMessage: Message = {
            id: uuidv4(),
            type: 'ai',
            content: configResponse.message,
            timestamp: new Date(),
            metadata: {
              suggestedActions: configResponse.suggested_actions || [],
              configState: configResponse.status,
              currentParams: configResponse.config
            }
          }
          
          setMessages(prev => [...prev, aiMessage])
          
        // 更新配置状态（但不要自动退出配置模式）
        setConfigMode(prev => ({
          ...prev,
          isActive: true,  // 确保配置模式保持激活
          currentState: configResponse.status,
          currentParams: configResponse.config
        }))
          
          // 不再根据状态自动退出配置模式
          // 只有当用户点击"完成配置"按钮时才退出
        } else {
          // 配置更新失败，提供帮助信息
          const aiMessage: Message = {
            id: uuidv4(),
            type: 'ai',
            content: configResponse.message,
            timestamp: new Date(),
            metadata: {
              suggestedActions: configResponse.suggested_actions || []
            }
          }
          
          setMessages(prev => [...prev, aiMessage])
        }
      } else {
        // 普通对话模式：使用AI服务处理纯对话
        const aiResponse = await aiService.processDialogue(content, {
          currentState,
          sessionId
        })

        // Add AI response
        const aiMessage: Message = {
          id: uuidv4(),
          type: 'ai',
          content: aiResponse.content,
          timestamp: new Date(),
          metadata: {
            suggestedActions: aiResponse.suggestedActions
          }
        }

        setMessages(prev => [...prev, aiMessage])
      }

    } catch (error) {
      console.error('Dialogue error:', error)
      const errorMessage = '抱歉，处理您的请求时出现了错误。请稍后重试。'
      setError(errorMessage)
      
      const aiErrorMessage: Message = {
        id: uuidv4(),
        type: 'ai',
        content: errorMessage,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, aiErrorMessage])
    } finally {
      setIsLoading(false)
    }
  }


  const handleError = (errorMessage: string) => {
    setError(errorMessage)
    message.error(errorMessage)
  }

  const handleActionClick = async (action: string) => {
    // 检查是否是报表类型按钮
    if (['稳态分析', '功能计算', '状态评估', '完整报表'].includes(action)) {
      await handleReportTypeClick(action)
    } else {
      // 其他建议按钮，正常发送消息
      handleSendMessage(action)
    }
  }

  const handleReportTypeClick = async (reportType: string) => {
    if (!sessionId) return

    setIsLoading(true)
    
    try {
      // 调用新的配置对话API开始配置流程
      const response = await fetch('/api/config-dialogue/start-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          report_type: reportType,
          user_id: sessionId
        })
      })
      
      const configResponse = await response.json()
      
      if (!response.ok) {
        throw new Error(configResponse.detail || '启动配置失败')
      }
      
      // 进入配置模式
      setConfigMode({
        isActive: true,
        sessionId: configResponse.session_id,
        currentState: configResponse.status,
        reportType: reportType,
        currentParams: configResponse.config || {}
      })
      
      // 添加AI响应消息
      const aiMessage: Message = {
        id: uuidv4(),
        type: 'ai',
        content: configResponse.message,
        timestamp: new Date(),
        metadata: {
          suggestedActions: ['使用转速通道', '使用温度通道', '阈值改成15000', '使用平均值'],
          configState: configResponse.status,
          currentParams: configResponse.config,
          sessionId: configResponse.session_id
        }
      }
      
      setMessages(prev => [...prev, aiMessage])
      
    } catch (error) {
      console.error('Report config error:', error)
      const errorMessage = '抱歉，启动报表配置时出现了错误。请稍后重试。'
      
      const aiErrorMessage: Message = {
        id: uuidv4(),
        type: 'ai',
        content: errorMessage,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, aiErrorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileUploaded = async (fileInfo: any) => {
    // 自动调用分析API获取通道统计信息
    try {
      const analysisResult = await apiService.getFileChannels(fileInfo.file_id)
      
      if (analysisResult && analysisResult.channels) {
        // 更新fileInfo包含分析结果
        fileInfo.analysis = {
          success: true,
          ...analysisResult
        }
      }
    } catch (error: any) {
      console.error('分析文件失败:', error)
      
      // 更新fileInfo包含分析错误
      fileInfo.analysis = {
        success: false,
        error: error.response?.data?.detail || error.message || '未知错误'
      }
    }
    
    // 添加文件上传成功的系统消息
    const fileMessage: Message = {
      id: uuidv4(),
      type: 'system',
      content: '', // 内容为空，因为会通过FileAnalysisResult组件显示
      timestamp: new Date(),
      metadata: {
        fileInfo
      }
    }
    
    setMessages(prev => [...prev, fileMessage])
    
    // 文件上传后自动进入配置模式 - 默认开始完整报表配置
    setIsLoading(true)
    try {
      const response = await fetch('/api/config-dialogue/start-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          report_type: '完整报表',
          user_id: sessionId
        })
      })
      
      const configResponse = await response.json()
      
      if (!response.ok) {
        throw new Error(configResponse.detail || '启动配置失败')
      }
      
      // 进入配置模式
      setConfigMode({
        isActive: true,
        sessionId: configResponse.session_id,
        currentState: configResponse.status,
        reportType: '完整报表',
        currentParams: configResponse.config || {}
      })
      
      // 添加AI响应消息
      const aiResponse: Message = {
        id: uuidv4(),
        type: 'ai',
        content: `太好了！我已经成功接收了您的数据文件 "${fileInfo.filename}"。\n\n我已经自动为您开启了报表配置模式。您可以通过自然语言来配置报表参数，或者直接点击下方按钮进行快速设置。\n\n配置完成后，请点击上方的"完成配置"按钮开始生成报表。\n\n支持的配置项：\n• 选择数据通道（转速、温度、压力等）\n• 设置分析阈值\n• 选择统计方法\n• 设置时间窗口`,
        timestamp: new Date(),
        metadata: {
          suggestedActions: ['使用转速通道', '使用温度通道', '使用压力通道', '设置阈值'],
          configState: configResponse.status,
          currentParams: configResponse.config,
          sessionId: configResponse.session_id
        }
      }
      
      setMessages(prev => [...prev, aiResponse])
      
    } catch (error) {
      console.error('启动配置失败:', error)
      
      // 如果配置启动失败，提供备用响应
      const aiResponse: Message = {
        id: uuidv4(),
        type: 'ai',
        content: `太好了！我已经成功接收了您的数据文件 "${fileInfo.filename}"。\n\n请告诉我您希望进行什么样的分析：\n\n• 稳态分析\n• 功能计算\n• 状态评估\n• 完整报表（依次生成以上三种报表）`,
        timestamp: new Date(),
        metadata: {
          suggestedActions: ['稳态分析', '功能计算', '状态评估', '完整报表']
        }
      }
      
      setMessages(prev => [...prev, aiResponse])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 配置状态栏 */}
      {configMode.isActive && (
        <div style={{ padding: '16px 16px 8px 16px', flexShrink: 0 }}>
          <ConfigStatusBar
          onCompleteConfig={handleCompleteConfig}
          onCancelConfig={handleCancelConfig}
          onConfigChange={(config) => {
            setConfigMode(prev => ({
              ...prev,
              currentParams: config
            }))
          }}
          isActive={configMode.isActive}
          reportType={configMode.reportType}
          currentState={configMode.currentState}
          currentParams={configMode.currentParams}
          sessionId={configMode.sessionId}
        />
        </div>
      )}
      
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <ChatContainer
          ref={chatContainerRef}
          messages={messages}
          currentState={currentState}
          isLoading={isLoading}
          onSendMessage={handleSendMessage}
          onError={handleError}
          onActionClick={handleActionClick}
          onFileUploaded={handleFileUploaded}
        />
      </div>
    </div>
  )
}

export default ChatPage
