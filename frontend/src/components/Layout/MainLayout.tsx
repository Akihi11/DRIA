import React from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import { 
  HomeOutlined, 
  MessageOutlined, 
  FileTextOutlined,
  RobotOutlined
} from '@ant-design/icons'

const { Header, Content } = Layout

const MainLayout: React.FC = () => {
  const location = useLocation()

  const menuItems = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: <Link to="/">首页</Link>,
    },
    {
      key: '/chat',
      icon: <MessageOutlined />,
      label: <Link to="/chat">AI对话</Link>,
    },
    {
      key: '/reports',
      icon: <FileTextOutlined />,
      label: <Link to="/reports">报表管理</Link>,
    },
  ]

  return (
    <Layout className="main-layout">
      <Header className="main-header">
        <div className="header-content">
          <Link to="/" className="logo">
            <RobotOutlined style={{ marginRight: 8 }} />
            DRIA AI报表生成系统
          </Link>
          <Menu
            theme="dark"
            mode="horizontal"
            selectedKeys={[location.pathname]}
            items={menuItems}
            className="nav-menu"
            style={{ flex: 1, justifyContent: 'center' }}
          />
        </div>
      </Header>
      <Content className="main-content">
        <div className="page-container">
          <div className="content-area">
            <Outlet />
          </div>
        </div>
      </Content>
    </Layout>
  )
}

export default MainLayout
