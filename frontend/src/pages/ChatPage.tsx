import React, { useState, useEffect, useRef } from 'react'
import { message } from 'antd'
import ChatContainer, { ChatContainerRef } from '../components/Chat/ChatContainer'
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
      // 使用AI服务处理纯对话
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

  const handleActionClick = (action: string) => {
    // 建议按钮，正常发送消息
    handleSendMessage(action)
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
    
    // 添加AI响应消息
    const aiResponse: Message = {
      id: uuidv4(),
      type: 'ai',
      content: `太好了！我已经成功接收了您的数据文件 "${fileInfo.filename}"。现在请告诉我您希望进行什么样的分析？比如：\n\n• 稳态分析\n• 功能计算\n• 状态评估\n• 完整报表（依次生成以上三种报表）\n\n请描述您的分析需求，我会为您生成相应的报表。`,
      timestamp: new Date(),
      metadata: {
        suggestedActions: ['稳态分析', '功能计算', '状态评估', '完整报表']
      }
    }
    
    setMessages(prev => [...prev, aiResponse])
  }

  return (
    <div style={{ height: '100%' }}>
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
  )
}

export default ChatPage
