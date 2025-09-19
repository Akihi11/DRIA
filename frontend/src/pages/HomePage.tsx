import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Row, Col, Card, Button, Typography, Space, Divider } from 'antd'
import { 
  RobotOutlined, 
  FileTextOutlined, 
  UploadOutlined,
  MessageOutlined,
  LineChartOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  StarOutlined
} from '@ant-design/icons'

const { Title, Paragraph, Text } = Typography

const HomePage: React.FC = () => {
  const navigate = useNavigate()

  const features = [
    {
      icon: <RobotOutlined style={{ fontSize: 32, color: '#1890ff' }} />,
      title: 'AI智能对话',
      description: '通过自然语言对话，轻松配置和生成报表',
    },
    {
      icon: <LineChartOutlined style={{ fontSize: 32, color: '#52c41a' }} />,
      title: '多维度分析',
      description: '支持稳态分析、功能计算、状态评估等多种分析维度',
    },
    {
      icon: <SafetyCertificateOutlined style={{ fontSize: 32, color: '#faad14' }} />,
      title: '专业可靠',
      description: '基于严格的算法标准，确保分析结果的准确性和可靠性',
    },
    {
      icon: <ThunderboltOutlined style={{ fontSize: 32, color: '#f5222d' }} />,
      title: '高效快速',
      description: '自动化处理流程，大幅提升报表生成效率',
    },
  ]

  const steps = [
    {
      step: 1,
      title: '上传数据文件',
      description: '支持CSV、Excel格式的时序数据文件',
    },
    {
      step: 2,
      title: 'AI对话配置',
      description: '通过自然语言描述您的分析需求',
    },
    {
      step: 3,
      title: '生成专业报表',
      description: '获得包含图表和分析结果的完整报表',
    },
  ]

  return (
    <div style={{ padding: '24px', height: '100%', overflow: 'auto' }}>
      {/* Hero Section */}
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <RobotOutlined style={{ fontSize: 64, color: '#1890ff', marginBottom: 16 }} />
        <Title level={1} style={{ marginBottom: 16 }}>
          DRIA AI报表生成系统
        </Title>
        <Paragraph style={{ fontSize: 18, color: '#666', maxWidth: 600, margin: '0 auto 32px' }}>
          基于人工智能的专业报表生成平台，通过智能对话快速生成高质量的数据分析报表
        </Paragraph>
        <Space size="large">
          <Button 
            type="primary" 
            size="large" 
            icon={<MessageOutlined />}
            onClick={() => navigate('/chat')}
          >
            开始对话
          </Button>
          <Button 
            size="large" 
            icon={<FileTextOutlined />}
            onClick={() => navigate('/reports')}
          >
            查看报表
          </Button>
        </Space>
      </div>

      <Divider />

      {/* Features Section */}
      <div style={{ marginBottom: 48 }}>
        <Title level={2} style={{ textAlign: 'center', marginBottom: 32 }}>
          核心功能
        </Title>
        <Row gutter={[24, 24]}>
          {features.map((feature, index) => (
            <Col xs={24} sm={12} lg={6} key={index}>
              <Card 
                hoverable
                style={{ height: '100%', textAlign: 'center' }}
                bodyStyle={{ padding: '24px 16px' }}
              >
                <div style={{ marginBottom: 16 }}>
                  {feature.icon}
                </div>
                <Title level={4} style={{ marginBottom: 8 }}>
                  {feature.title}
                </Title>
                <Paragraph style={{ color: '#666', fontSize: 14 }}>
                  {feature.description}
                </Paragraph>
              </Card>
            </Col>
          ))}
        </Row>
      </div>

      <Divider />

      {/* How it works */}
      <div style={{ marginBottom: 48 }}>
        <Title level={2} style={{ textAlign: 'center', marginBottom: 32 }}>
          使用流程
        </Title>
        <Row gutter={[24, 24]} justify="center">
          {steps.map((step, index) => (
            <Col xs={24} md={8} key={index}>
              <Card 
                style={{ textAlign: 'center', height: '100%' }}
                bodyStyle={{ padding: '32px 24px' }}
              >
                <div 
                  style={{ 
                    width: 48, 
                    height: 48, 
                    borderRadius: '50%', 
                    background: '#1890ff', 
                    color: 'white', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center', 
                    fontSize: 20, 
                    fontWeight: 'bold',
                    margin: '0 auto 16px'
                  }}
                >
                  {step.step}
                </div>
                <Title level={4} style={{ marginBottom: 8 }}>
                  {step.title}
                </Title>
                <Paragraph style={{ color: '#666' }}>
                  {step.description}
                </Paragraph>
              </Card>
            </Col>
          ))}
        </Row>
      </div>

      <Divider />

      {/* CTA Section */}
      <div style={{ textAlign: 'center', background: '#fafafa', padding: '48px 24px', borderRadius: 8 }}>
        <Title level={3} style={{ marginBottom: 16 }}>
          准备好开始了吗？
        </Title>
        <Paragraph style={{ fontSize: 16, color: '#666', marginBottom: 24 }}>
          上传您的数据文件，让AI帮您生成专业的分析报表
        </Paragraph>
        <Button 
          type="primary" 
          size="large" 
          icon={<UploadOutlined />}
          onClick={() => navigate('/chat')}
        >
          立即开始
        </Button>
      </div>
    </div>
  )
}

export default HomePage
