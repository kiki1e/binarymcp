import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import type { ReactNode } from 'react'

const NAV = [
  { path: '/analysis', label: 'Analysis' },
  { path: '/keys', label: 'Keys' },
  { path: '/models', label: 'Models' },
  { path: '/explore', label: 'Explore' },
  { path: '/leaderboard', label: 'Stats' },
]

export default function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const { username, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen flex flex-col">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <Link to="/" className="text-xl font-bold text-emerald-400">
          BinaryMCP
        </Link>
        <div className="flex items-center gap-6">
          {NAV.map((n) => (
            <Link
              key={n.path}
              to={n.path}
              className={`text-sm ${
                pathname.startsWith(n.path) ? 'text-emerald-400' : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              {n.label}
            </Link>
          ))}
          <span className="text-sm text-gray-500">{username}</span>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-400 hover:text-red-400"
          >
            Logout
          </button>
        </div>
      </nav>
      <main className="flex-1 px-6 py-8 max-w-7xl mx-auto w-full">
        {children}
      </main>
      <footer className="border-t border-gray-800 px-6 py-4 text-center text-xs text-gray-500">
        BinaryMCP - CTF Challenge Analysis Platform
      </footer>
    </div>
  )
}
