import React, { useState, useRef, useEffect, forwardRef, useImperativeHandle, useCallback } from 'react'
import { Layout, Input, Button, Space, Spin, Tooltip } from 'antd'
import { 
  SendOutlined, 
  RobotOutlined,
  AudioOutlined,
  StopOutlined
} from '@ant-design/icons'
import MessageBubble from './MessageBubble'
import FileUploadButton from '../FileUpload/FileUploadButton'
import { Message } from '../../types/store'
import { DialogueState } from '../../types/api'
import { useSpeechRecognition } from '../../hooks/useSpeechRecognition'
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
  
  // 保存录音开始前的输入值
  const inputBeforeRecordingRef = useRef('')
  
  const latestErrorHandlerRef = useRef(onError)

  useEffect(() => {
    latestErrorHandlerRef.current = onError
  }, [onError])

  const handleSpeechResult = useCallback((text: string, isFinal: boolean) => {
    if (isFinal) {
      const baseText = inputBeforeRecordingRef.current.trim()
      const newValue = baseText 
        ? `${baseText} ${text.trim()}` 
        : text.trim()
      setInputValue(newValue)
      inputBeforeRecordingRef.current = newValue
    } else {
      const baseText = inputBeforeRecordingRef.current.trim()
      const displayValue = baseText 
        ? `${baseText} ${text.trim()}` 
        : text.trim()
      setInputValue(displayValue)
    }
  }, [])

  const handleSpeechError = useCallback((error: string) => {
    latestErrorHandlerRef.current?.(error)
  }, [])

  // 语音识别
  const {
    isSupported,
    isListening,
    transcript,
    startListening,
    stopListening,
    error: speechError
  } = useSpeechRecognition({
    lang: 'zh-CN',
    continuous: false,
    interimResults: true,
    onResult: handleSpeechResult,
    onError: handleSpeechError
  })

  // 当停止录音时，更新基础值（用于下次录音）
  useEffect(() => {
    if (!isListening && transcript) {
      // 录音结束后，将最终结果保存为基础值
      const finalValue = inputValue.trim()
      if (finalValue) {
        inputBeforeRecordingRef.current = finalValue
      }
    }
  }, [isListening, transcript, inputValue])

  // 处理语音识别错误
  useEffect(() => {
    if (speechError) {
      latestErrorHandlerRef.current?.(speechError)
    }
  }, [speechError])

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
    
    // 如果正在录音，先停止
    if (isListening) {
      stopListening()
    }
    
    const content = inputValue.trim()
    setInputValue('')
    onSendMessage(content)
  }

  const handleToggleVoiceInput = () => {
    if (isListening) {
      stopListening()
    } else {
      // 开始录音前，保存当前输入值
      inputBeforeRecordingRef.current = inputValue
      startListening()
    }
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
                disabled={isInputDisabled || isListening}
                autoSize={{ minRows: 1, maxRows: 4 }}
                style={{ flex: 1 }}
              />
              {isSupported && (
                <Tooltip title={isListening ? '点击停止录音' : '点击开始语音输入'}>
                  <Button
                    type={isListening ? 'primary' : 'default'}
                    danger={isListening}
                    icon={isListening ? <StopOutlined /> : <AudioOutlined />}
                    onClick={handleToggleVoiceInput}
                    disabled={isInputDisabled}
                    className={isListening ? 'voice-button-recording' : 'voice-button'}
                  />
                </Tooltip>
              )}
              <FileUploadButton
                onFileUploaded={handleFileUploaded}
                onUploadError={handleFileUploadError}
                disabled={isInputDisabled || isListening}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSendMessage}
                disabled={!inputValue.trim() || isInputDisabled || isListening}
              >
                发送
              </Button>
            </Space.Compact>
          </div>
          {isListening && (
            <div className="voice-recording-indicator">
              <span className="recording-dot"></span>
              <span>正在录音中...</span>
            </div>
          )}
        </div>
      </Footer>
    </Layout>
  )
})

ChatContainer.displayName = 'ChatContainer'

export default ChatContainer