import React, { useState, useEffect, useRef } from 'react'
import { message } from 'antd'
import ChatContainer, { ChatContainerRef } from '../components/Chat/ChatContainer'
import { Message } from '../types/store'
import { DialogueState } from '../types/api'
import apiService from '../services/api'
import aiService from '../services/aiService'
import { v4 as uuidv4 } from 'uuid'

const ChatPage: React.FC = () => {
  const [sessionId, setSessionId] = useState<string>('')
  const [messages, setMessages] = useState<Message[]>([])
  const [currentState, setCurrentState] = useState<DialogueState>(DialogueState.INITIAL)
  const [isLoading, setIsLoading] = useState(false)
  const [, setError] = useState<string | null>(null)
  const chatContainerRef = useRef<ChatContainerRef>(null)

  // Initialize session on component mount
  useEffect(() => {
    const newSessionId = uuidv4()
    setSessionId(newSessionId)
    
    // 不添加预设欢迎消息，让用户主动开始对话
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
      const aiResponse = await aiService.processDialogue(content, null, {
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
      />
    </div>
  )
}

export default ChatPage
