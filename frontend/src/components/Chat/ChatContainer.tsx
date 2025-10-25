import React, { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react'
import { Layout, Input, Button, Space, Spin } from 'antd'
import { 
  SendOutlined, 
  RobotOutlined
} from '@ant-design/icons'
import MessageBubble from './MessageBubble'
import FileUploadButton from '../FileUpload/FileUploadButton'
import { Message } from '../../types/store'
import { DialogueState } from '../../types/api'
import './ChatContainer.css'

const { Content, Footer } = Layout
const { TextArea } = Input

export interface ChatContainerRef {
  // 文件上传功能
  uploadFile: () => void
}

interface ChatContainerProps {
  messages: Message[]
  currentState: DialogueState
  isLoading: boolean
  onSendMessage: (content: string) => void
  onError: (error: string) => void
  onActionClick?: (action: string) => void
  onFileUploaded?: (fileInfo: any) => void
}

const ChatContainer = forwardRef<ChatContainerRef, ChatContainerProps>(({
  messages,
  currentState,
  isLoading,
  onSendMessage,
  onError,
  onActionClick,
  onFileUploaded
}, ref) => {
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Expose methods to parent component
  useImperativeHandle(ref, () => ({
    uploadFile: () => {
      // 触发文件上传
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
      fileInput?.click()
    }
  }))

  const handleSendMessage = () => {
    if (!inputValue.trim()) return
    
    const content = inputValue.trim()
    setInputValue('')
    onSendMessage(content)
  }

  const handleFileUploaded = (fileInfo: any) => {
    // 这里需要调用父组件的消息添加方法
    // 暂时通过onFileUploaded回调传递文件信息
    onFileUploaded?.(fileInfo)
  }

  const handleFileUploadError = (error: string) => {
    onError(error)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const getPlaceholder = () => {
    return '请输入您的问题或需求...'
  }

  const isInputDisabled = currentState === DialogueState.ERROR || isLoading

  return (
    <Layout className="chat-container">
      <Content className="messages-area">
        <div className="messages-wrapper">
          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              isLoading={message.id === 'loading'}
              onActionClick={onActionClick}
            />
          ))}
          
          {isLoading && (
            <div className="message-item ai-message">
              <div className="message-avatar">
                <RobotOutlined />
              </div>
              <div className="message-content">
                <Spin size="small" />
                <span style={{ marginLeft: 8 }}>AI正在思考中...</span>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </Content>
      
      <Footer className="input-area">
        <div className="input-wrapper">
          <div className="input-controls">
            <Space.Compact style={{ width: '100%' }}>
              <TextArea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={getPlaceholder()}
                disabled={isInputDisabled}
                autoSize={{ minRows: 1, maxRows: 4 }}
                style={{ flex: 1 }}
              />
              <FileUploadButton
                onFileUploaded={handleFileUploaded}
                onUploadError={handleFileUploadError}
                disabled={isInputDisabled}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSendMessage}
                disabled={!inputValue.trim() || isInputDisabled}
              >
                发送
              </Button>
            </Space.Compact>
          </div>
        </div>
      </Footer>
    </Layout>
  )
})

ChatContainer.displayName = 'ChatContainer'

export default ChatContainer