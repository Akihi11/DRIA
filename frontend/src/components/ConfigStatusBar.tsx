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

  // 渲染配置参数
  const renderConfigParams = () => {
    if (!currentParams) return null

    const config = currentParams
    const params = []

    // 通道配置
    if (config.use_rpm_channel !== undefined) {
      params.push(
        <Tag key="rpm" color={config.use_rpm_channel ? 'green' : 'default'}>
          转速通道: {config.use_rpm_channel ? '启用' : '禁用'}
        </Tag>
      )
    }
    
    if (config.use_temperature_channel !== undefined) {
      params.push(
        <Tag key="temp" color={config.use_temperature_channel ? 'green' : 'default'}>
          温度通道: {config.use_temperature_channel ? '启用' : '禁用'}
        </Tag>
      )
    }
    
    if (config.use_pressure_channel !== undefined) {
      params.push(
        <Tag key="pressure" color={config.use_pressure_channel ? 'green' : 'default'}>
          压力通道: {config.use_pressure_channel ? '启用' : '禁用'}
        </Tag>
      )
    }

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

    // 时间窗口
    if (config.time_window !== undefined) {
      params.push(
        <Tag key="time" color="orange">
          时间窗口: {config.time_window}{config.time_unit || '分钟'}
        </Tag>
      )
    }

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
      default:
        return <Tag color="default">未知状态</Tag>
    }
  }

  // 获取按钮文本
  const getButtonText = () => {
    switch (currentState) {
      case 'configuring':
        return '完成配置'
      case 'confirming':
        return '确认生成报表'
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
