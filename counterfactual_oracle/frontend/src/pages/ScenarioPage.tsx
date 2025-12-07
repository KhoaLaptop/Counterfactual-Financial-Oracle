import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { scenariosApi } from '../lib/api'
import { useScenarioStatus } from '../hooks/useScenarioStatus'
import { Scenario } from '../lib/types'
import ScenarioCharts from '../components/ScenarioCharts'
import DebateViewer from '../components/DebateViewer'
import { useState, useEffect } from 'react'

export default function ScenarioPage() {
  const { scenarioId } = useParams<{ scenarioId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [downloading, setDownloading] = useState(false)

  const { data: scenario, isLoading, refetch } = useQuery<Scenario>({
    queryKey: ['scenario', scenarioId],
    queryFn: () => scenariosApi.get(scenarioId!),
    enabled: !!scenarioId,
  })

  const { data: status } = useScenarioStatus(scenarioId || null, !!scenarioId)

  // Auto-refetch scenario data when status changes to COMPLETED
  useEffect(() => {
    if (status?.status === 'COMPLETED' && scenario?.status !== 'COMPLETED') {
      refetch()
    }
  }, [status?.status, scenario?.status, refetch])

  const handleDownloadReport = async () => {
    if (!scenarioId) return

    setDownloading(true)
    try {
      const blob = await scenariosApi.generateReport(scenarioId)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `scenario_${scenarioId}_report.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to download report')
    } finally {
      setDownloading(false)
    }
  }

  // Get verdict color based on the verdict text
  const getVerdictColor = (verdict: string) => {
    const v = verdict.toLowerCase()
    if (v.includes('buy') || v.includes('bullish')) {
      return 'text-green-400'
    } else if (v.includes('sell') || v.includes('bearish')) {
      return 'text-red-400'
    } else if (v.includes('hold') || v.includes('cautious')) {
      return 'text-yellow-400'
    }
    return 'text-blue-400'
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  if (!scenario) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-4">Scenario not found</h2>
          <button onClick={() => navigate('/')} className="btn-primary">
            Go Home
          </button>
        </div>
      </div>
    )
  }

  const isRunning = scenario.status === 'RUNNING' || scenario.status === 'PENDING'
  const isCompleted = scenario.status === 'COMPLETED'
  const isFailed = scenario.status === 'FAILED'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => navigate(-1)}
          className="text-blue-400 hover:text-blue-300 mb-4 flex items-center gap-1"
        >
          ← Back
        </button>
        <h1 className="text-2xl font-semibold text-white mb-2">
          {scenario.name || 'Scenario Analysis'}
        </h1>
        <div className="flex items-center gap-4">
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${isCompleted ? 'bg-green-500/20 text-green-400 border border-green-500/30' :
              isFailed ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
            }`}>
            {scenario.status}
          </span>
          {isRunning && (
            <span className="text-sm text-gray-400">
              Progress: {status?.progress || scenario.progress}%
            </span>
          )}
        </div>
      </div>

      {/* Error Message */}
      {isFailed && scenario.error_message && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-red-400 mb-2">Error</h3>
          <p className="text-red-300">{scenario.error_message}</p>
        </div>
      )}

      {/* Loading State */}
      {isRunning && (
        <div className="card text-center py-12">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mb-4"></div>
          <p className="text-gray-400">
            Running Monte Carlo simulation and AI analysis...
            <br />
            This may take 30-60 seconds
          </p>
          {status && (
            <div className="mt-4 max-w-md mx-auto">
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${status.progress}%` }}
                ></div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Results */}
      {isCompleted && scenario.simulation_results && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="card">
              <p className="text-sm text-gray-400 mb-1">Projected NPV</p>
              <p className="text-2xl font-bold text-white">
                ${scenario.simulation_results.median_npv.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
              <p className="text-xs text-gray-500 mt-1">Net Present Value</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-400 mb-1">Median Revenue</p>
              <p className="text-2xl font-bold text-green-400">
                ${scenario.simulation_results.median_revenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
              <p className="text-xs text-gray-500 mt-1">Projected annual revenue</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-400 mb-1">Median EBITDA</p>
              <p className="text-2xl font-bold text-blue-400">
                ${scenario.simulation_results.median_ebitda.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
              <p className="text-xs text-gray-500 mt-1">Earnings before interest, tax, D&A</p>
            </div>
          </div>

          {/* Charts */}
          <div className="card">
            <h2 className="text-xl font-semibold text-white mb-4">Simulation Results</h2>
            <ScenarioCharts simulation={scenario.simulation_results} />
          </div>

          {/* Assumption Log */}
          {scenario.simulation_results.assumption_log && (
            <div className="card">
              <h2 className="text-xl font-semibold text-white mb-4">Model Assumptions</h2>
              <ul className="space-y-2">
                {scenario.simulation_results.assumption_log.map((log, idx) => (
                  <li key={idx} className="text-gray-300">• {log}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Critic Verdict */}
          {scenario.critic_verdict && (
            <div className="card">
              <h2 className="text-xl font-semibold text-white mb-4">Adversarial Analysis</h2>
              <div className={`inline-block px-3 py-1 rounded-full text-sm font-medium mb-4 ${scenario.critic_verdict.verdict === 'approve'
                  ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                  : 'bg-red-500/20 text-red-400 border border-red-500/30'
                }`}>
                VERDICT: {scenario.critic_verdict.verdict.toUpperCase()}
              </div>
              <div className="space-y-2">
                {scenario.critic_verdict.comparative_analysis.map((point, idx) => (
                  <p key={idx} className="text-gray-300">{point}</p>
                ))}
              </div>
            </div>
          )}

          {/* Debate */}
          {scenario.debate_result && (
            <div className="card">
              <h2 className="text-xl font-semibold text-white mb-4">AI Analyst Debate</h2>
              <DebateViewer debate={scenario.debate_result} />
            </div>
          )}

          {/* Final Verdict */}
          {scenario.final_verdict && (
            <div className="card text-center py-8">
              <h2 className="text-lg font-semibold text-gray-400 mb-2">Final Investment Verdict</h2>
              <p className={`text-4xl font-bold mb-2 ${getVerdictColor(scenario.final_verdict)}`}>
                {scenario.final_verdict}
              </p>
              {scenario.debate_result && (
                <p className="text-gray-500">Confidence: {scenario.debate_result.confidence_level}</p>
              )}
            </div>
          )}

          {/* Download Report */}
          <div className="text-center">
            <button
              onClick={handleDownloadReport}
              disabled={downloading}
              className="btn-primary"
            >
              {downloading ? 'Generating...' : '📥 Download PDF Report'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
