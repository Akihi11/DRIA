import React from 'react'
import { Button, Card, Tag, Space, Typography } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, SettingOutlined } from '@ant-design/icons'
import './ConfigStatusBar.css'

const { Title } = Typography

interface ConfigStatusBarProps {
  onCompleteConfig: () => void
  onCancelConfig: () => void
  onConfigChange?: (config: any) => void
  isActive?: boolean  // 添加父组件传入的状态
  reportType?: string
  currentState?: string
  currentParams?: any
  sessionId?: string
}

const ConfigStatusBar: React.FC<ConfigStatusBarProps> = (props) => {
  const {
    onCompleteConfig,
    onCancelConfig,
    onConfigChange,
    isActive = false,
    reportType = '',
    currentState = '',
    currentParams = {},
    sessionId = ''
  } = props
  
  // 处理完成配置 - 直接调用父组件的回调
  const handleCompleteClick = () => {
    onCompleteConfig()
  }

  // 处理取消配置 - 直接调用父组件的回调
  const handleCancelClick = () => {
    onCancelConfig()
  }

  // 渲染配置参数（仅在参数配置阶段显示，初始阶段不显示）
  const renderConfigParams = () => {
    if (!currentParams) return null
    
    // 在通道选择阶段不显示任何参数标签
    const configState = currentState || ''
    if (configState === 'display_channels' || configState === 'trigger_combo' || !configState) {
      return null
    }

    const config = currentParams
    const params = []

    // 阈值配置
    if (config.threshold !== undefined) {
      params.push(
        <Tag key="threshold" color="blue">
          阈值: {config.threshold}
        </Tag>
      )
    }

    // 统计方法
    if (config.statistical_method) {
      params.push(
        <Tag key="method" color="purple">
          统计方法: {config.statistical_method}
        </Tag>
      )
    }

    // 时间窗口已移除，不再显示

    return params
  }

  // 获取状态标签
  const getStatusTag = () => {
    switch (currentState) {
      case 'configuring':
        return <Tag color="processing" icon={<SettingOutlined />}>配置中</Tag>
      case 'confirming':
        return <Tag color="warning" icon={<CheckCircleOutlined />}>确认中</Tag>
      case 'completed':
        return <Tag color="success" icon={<CheckCircleOutlined />}>已完成</Tag>
      case 'cancelled':
        return <Tag color="error" icon={<CloseCircleOutlined />}>已取消</Tag>
      case 'display_channels':
        return <Tag color="processing" icon={<SettingOutlined />}>通道选择</Tag>
      case 'select_rpm_standard':
        return <Tag color="processing" icon={<SettingOutlined />}>选择判断标准</Tag>
      case 'trigger_combo':
        return <Tag color="processing" icon={<SettingOutlined />}>条件配置</Tag>
      case 'parameter_config':
        return <Tag color="processing" icon={<SettingOutlined />}>参数配置</Tag>
      case 'confirmation':
        return <Tag color="warning" icon={<CheckCircleOutlined />}>确认配置</Tag>
      case 'initial':
        return <Tag color="default" icon={<SettingOutlined />}>等待选择</Tag>
      default:
        return <Tag color="processing" icon={<SettingOutlined />}>配置中</Tag>
    }
  }

  // 获取按钮文本
  const getButtonText = () => {
    switch (currentState) {
      case 'configuring':
        return '完成配置'
      case 'confirming':
        return '确认生成报表'
      case 'initial':
        return '等待选择报表类型' // 在等待选择报表类型时禁用按钮
      default:
        return '完成配置'
    }
  }

  if (!isActive) {
    return null
  }

  return (
    <Card className="config-status-bar" size="small">
      <div className="config-status-content">
        <div className="config-info">
          <Space align="center">
            <SettingOutlined className="config-icon" />
            <Title level={5} className="config-title">
              {reportType || '配置'}
            </Title>
            {getStatusTag()}
          </Space>
          
          <div className="config-params">
            <Space wrap>
              {renderConfigParams()}
            </Space>
          </div>
        </div>
        
        <div className="config-actions" style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            onClick={handleCompleteClick}
            className="complete-btn"
            disabled={currentState === 'initial'} // 等待选择报表类型时禁用
          >
            {getButtonText()}
          </Button>
          <Button
            icon={<CloseCircleOutlined />}
            onClick={handleCancelClick}
            className="cancel-btn"
          >
            取消配置
          </Button>
        </div>
      </div>
    </Card>
  )
}

export default ConfigStatusBar
