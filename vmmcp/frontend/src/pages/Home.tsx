import { Link } from 'react-router-dom'

const FEATURES = [
  { title: 'Real-time Monitoring', desc: 'Continuously scans GitHub public events for leaked API keys.' },
  { title: '16+ Providers', desc: 'OpenAI, Anthropic, Google, AWS, Stripe, Twilio and more.' },
  { title: 'Instant Detection', desc: 'Keys detected within minutes of being pushed to public repos.' },
]

export default function Home() {
  return (
    <div className="space-y-12">
      <section className="text-center space-y-4 py-12">
        <h1 className="text-4xl font-bold">GitHub Key Monitor</h1>
        <p className="text-gray-400 max-w-xl mx-auto">
          Real-time detection and tracking of API key leaks across public GitHub repositories.
        </p>
        <Link
          to="/explore"
          className="inline-block mt-4 px-6 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition"
        >
          Explore Leaks
        </Link>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {FEATURES.map((f) => (
          <div key={f.title} className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h3 className="font-semibold text-emerald-400 mb-2">{f.title}</h3>
            <p className="text-sm text-gray-400">{f.desc}</p>
          </div>
        ))}
      </section>
    </div>
  )
}
