import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import Layout from './components/Layout'
import Explore from './pages/Explore'
import Leaderboard from './pages/Leaderboard'
import Login from './pages/Login'
import KeyManager from './pages/KeyManager'
import Analysis from './pages/Analysis'
import AnalysisResult from './pages/AnalysisResult'
import ModelPanel from './pages/ModelPanel'
import ApiConfig from './pages/ApiConfig'
import Chat from './pages/Chat'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={
        <ProtectedRoute>
          <Layout>
            <Routes>
              <Route path="/" element={<Navigate to="/analysis" replace />} />
              <Route path="/analysis" element={<Analysis />} />
              <Route path="/analysis/:taskId" element={<AnalysisResult />} />
              <Route path="/keys" element={<KeyManager />} />
              <Route path="/models" element={<ModelPanel />} />
              <Route path="/explore" element={<Explore />} />
              <Route path="/leaderboard" element={<Leaderboard />} />
              <Route path="/config" element={<ApiConfig />} />
              <Route path="/chat" element={<Chat />} />
            </Routes>
          </Layout>
        </ProtectedRoute>
      } />
    </Routes>
  )
}
