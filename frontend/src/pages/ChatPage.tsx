import React, { useState, useEffect, useRef } from 'react'
import { message, Modal, Checkbox, Space, Button } from 'antd'
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

  // 最近一次上传文件解析出的通道列表（用于稳态参数多选）
  const [lastFileChannels, setLastFileChannels] = useState<string[]>([])
  const [lastFileId, setLastFileId] = useState<string>("")
  const [channelModalVisible, setChannelModalVisible] = useState<boolean>(false)
  const [selectedChannels, setSelectedChannels] = useState<string[]>([])

  const containsNg = (name: string) => /(^|[^A-Za-z])Ng(\(|[^A-Za-z]|$)|转速|低压/.test(name)
  const containsNp = (name: string) => /(^|[^A-Za-z])Np(\(|[^A-Za-z]|$)|高压/.test(name)
  const containsTemp = (name: string) => /(温度|Temperature|°C)/i.test(name)
  const containsPressure = (name: string) => /(压力|Pressure|kPa)/i.test(name)

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
      const reportId = data.config?.report_id
      const aiMessage: Message = {
        id: uuidv4(),
        type: 'ai',
        content: data.message,
        timestamp: new Date(),
        metadata: {
          configState: data.status,
          currentParams: data.config,
          reportId: reportId  // 添加报表ID，用于下载
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
    if (['稳态分析', '稳态参数', '功能计算', '状态评估', '完整报表'].includes(action)) {
      // 如果点击的是稳态参数，转换为稳态分析
      const reportType = action === '稳态参数' ? '稳态分析' : action
      await handleReportTypeClick(reportType)
    } else {
      // 其他建议按钮，正常发送消息
      handleSendMessage(action)
    }
  }

  // 应用“稳态参数”通道选择
  const applySteadyStateChannelSelection = async () => {
    if (!configMode.sessionId) return

    // 校验：必须至少选择一个转速通道（Ng 或 Np）
    const hasNg = selectedChannels.some(c => containsNg(c))
    const hasNp = selectedChannels.some(c => containsNp(c))
    if (!hasNg && !hasNp) {
      message.warning('请至少选择一个转速通道（Ng 或 Np）')
      return
    }

    setIsLoading(true)
    try {
      // 1) 先选择所有通道
      for (const channel of selectedChannels) {
        await fetch('/api/config-dialogue/update-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: configMode.sessionId, user_input: `选择 ${channel}` })
        })
      }

      // 2) 调用"完成通道选择"，后端会返回默认条件一和二
      const response = await fetch('/api/config-dialogue/update-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: configMode.sessionId, user_input: '完成通道选择' })
      })

      const data = await response.json()
      
      if (!response.ok) {
        throw new Error(data.detail || '完成通道选择失败')
      }

      // 关闭弹窗
      setChannelModalVisible(false)

      // 显示后端返回的消息和建议操作
      // 使用后端返回的suggested_actions，不要使用后备选项
      const currentState = data.state || data.status
      console.log('[DEBUG] 完成通道选择后，后端返回:', {
        state: currentState,
        message: data.message,
        suggested_actions: data.suggested_actions,
        current_params: data.current_params
      })
      
      const aiMessage: Message = {
        id: uuidv4(),
        type: 'ai',
        content: data.message || '已选择通道',
        timestamp: new Date(),
        metadata: {
          suggestedActions: data.suggested_actions || [], // 直接使用后端返回的，不要后备选项
          configState: currentState,
          currentParams: data.current_params || data.config
        }
      }
      setMessages(prev => [...prev, aiMessage])

      // 更新配置状态
      setConfigMode(prev => ({
        ...prev,
        currentState: data.status || data.state,
        currentParams: data.current_params || data.config || prev.currentParams
      }))
    } catch (e) {
      message.error('应用通道选择失败，请重试')
    } finally {
      setIsLoading(false)
    }
  }

  // 将前端展示名称映射为后端识别的报表类型 key
  const mapReportTypeToBackend = (rt: string): string => {
    switch (rt) {
      case '稳态分析':
      case '稳态参数':
        return 'steady_state'
      case '功能计算':
        return 'function_calc'
      case '状态评估':
        return 'status_eval'
      case '完整报表':
        return 'complete'
      default:
        return rt
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
          report_type: mapReportTypeToBackend(reportType),
          user_id: sessionId,
          file_id: lastFileId || undefined
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

      // 若选择的是“稳态分析”，弹出通道多选弹窗，不显示AI消息
      if (reportType === '稳态分析') {
        const base = lastFileChannels && lastFileChannels.length > 0
          ? lastFileChannels
          : ['Ng(rpm)', 'Np(rpm)', 'Temperature(°C)', 'Pressure(kPa)']
        setSelectedChannels([])
        setChannelModalVisible(true)
        // 确保候选存在
        setLastFileChannels(base)
        // 有弹窗时不显示AI消息
      } else {
        // 非稳态分析，显示AI消息
        const fallbackActions = ['选择 Ng 转速通道', '选择 Np 转速通道', '选择温度通道', '选择压力通道', '确认配置', '取消配置']
        const aiMessage: Message = {
          id: uuidv4(),
          type: 'ai',
          content: configResponse.message,
          timestamp: new Date(),
          metadata: {
            suggestedActions: (configResponse.suggested_actions && configResponse.suggested_actions.length > 0)
              ? configResponse.suggested_actions
              : fallbackActions,
            configState: configResponse.status,
            currentParams: configResponse.config,
            sessionId: configResponse.session_id
          }
        }
        setMessages(prev => [...prev, aiMessage])
      }

      // 将选择的报表类型写入最近一次上传文件的元数据JSON
      if (lastFileId) {
        const form = new FormData()
        form.append('report_type', reportType)
        fetch(`/api/ai_report/meta/${lastFileId}/report_type`, {
          method: 'POST',
          body: form
        }).catch(() => {})
      }
      
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
    
    // 文件上传后：只给出报表类型选择，不自动进入配置
    // 记录可用通道名称供“稳态参数”弹窗使用
    try {
      const channelNames = (fileInfo?.analysis?.channels || []).map((c: any) => c.channel_name || c.name).filter(Boolean)
      if (channelNames.length > 0) {
        setLastFileChannels(channelNames)
      }
      if (fileInfo?.file_id) {
        setLastFileId(fileInfo.file_id)
      }
    } catch {}

    // 文件上传后自动进入配置模式（但不启动具体报表配置，等用户选择报表类型）
    // 显示配置横幅，状态为"等待选择报表类型"
    setConfigMode({
      isActive: true,
      sessionId: '', // 还未选择报表类型，暂时为空
      currentState: 'initial',
      reportType: '待选择',
      currentParams: {}
    })

    const aiResponse: Message = {
      id: uuidv4(),
      type: 'ai',
      content: `太好了！我已经成功接收了您的数据文件 "${fileInfo.filename}"。\n\n请先选择要生成的报表类型：`,
      timestamp: new Date(),
      metadata: {
        suggestedActions: ['稳态参数', '功能计算', '状态评估', '完整报表']
      }
    }
    setMessages(prev => [...prev, aiResponse])
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

      {/* 稳态参数 - 通道多选弹窗 */}
      <Modal
        title="请选择用于稳态参数的通道（至少包含一个转速通道）"
        open={channelModalVisible}
        onCancel={() => setChannelModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setChannelModalVisible(false)}>取消</Button>,
          <Button key="ok" type="primary" onClick={applySteadyStateChannelSelection}>确定</Button>
        ]}
      >
        <Checkbox.Group
          style={{ width: '100%' }}
          value={selectedChannels}
          onChange={(vals) => setSelectedChannels(vals as string[])}
        >
          <Space direction="vertical" style={{ width: '100%' }}>
            {lastFileChannels.map(name => (
              <Checkbox key={name} value={name}>{name}</Checkbox>
            ))}
          </Space>
        </Checkbox.Group>
      </Modal>
    </div>
  )
}

export default ChatPage
