import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { reportsApi, scenariosApi } from '../lib/api'
import { useState } from 'react'
import FinancialStatements from '../components/FinancialStatements'

export default function ReportPage() {
  const { reportId } = useParams<{ reportId: string }>()
  const navigate = useNavigate()
  const [opexDelta, setOpexDelta] = useState(0)
  const [revGrowthDelta, setRevGrowthDelta] = useState(0)
  const [discountRateDelta, setDiscountRateDelta] = useState(0)
  const [creating, setCreating] = useState(false)

  const { data: report, isLoading } = useQuery({
    queryKey: ['report', reportId],
    queryFn: () => reportsApi.get(reportId!),
    enabled: !!reportId,
  })

  const handleCreateScenario = async () => {
    if (!reportId) return

    setCreating(true)
    try {
      const scenario = await scenariosApi.create({
        report_id: reportId,
        revenue_growth_delta_bps: revGrowthDelta,
        opex_delta_bps: opexDelta,
        discount_rate_delta_bps: discountRateDelta,
      })
      navigate(`/scenarios/${scenario.id}`)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create scenario')
    } finally {
      setCreating(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-4">Report not found</h2>
          <button
            onClick={() => navigate('/')}
            className="btn-primary"
          >
            Go Home
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-white mb-1">
          {report.company_name || 'Financial Report'}
        </h1>
        {report.fiscal_year && (
          <p className="text-gray-400">Fiscal Year: {report.fiscal_year}</p>
        )}
      </div>

      {/* Financial Statements */}
      {report.report_data && (
        <FinancialStatements data={report.report_data} />
      )}

      {/* Create Scenario Card */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-xl font-semibold text-white mb-4">Create Scenario</h2>

        {/* Beginner's Guide Section */}
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 mb-6">
          <h3 className="text-sm font-semibold text-blue-400 mb-3 flex items-center gap-2">
            💡 New to Finance? Here's What These Mean:
          </h3>
          <div className="space-y-3 text-sm text-gray-300">
            <div className="flex items-start gap-2">
              <span className="text-green-400 font-bold">📈</span>
              <div>
                <span className="font-medium text-white">Revenue Growth Delta:</span>{' '}
                How much faster (or slower) do you think the company will grow?
                <span className="text-gray-500 block text-xs mt-0.5">
                  +100 bps = 1% faster growth than expected | -100 bps = 1% slower
                </span>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-orange-400 font-bold">💰</span>
              <div>
                <span className="font-medium text-white">OpEx Delta:</span>{' '}
                Will the company spend more or less on operations (salaries, marketing, etc.)?
                <span className="text-gray-500 block text-xs mt-0.5">
                  +100 bps = 1% more spending | -100 bps = 1% cost cutting
                </span>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-purple-400 font-bold">📊</span>
              <div>
                <span className="font-medium text-white">Discount Rate Delta:</span>{' '}
                How risky is this company? Higher risk = future money is worth less today.
                <span className="text-gray-500 block text-xs mt-0.5">
                  +100 bps = more risk (lower valuation) | -100 bps = less risk (higher valuation)
                </span>
              </div>
            </div>
          </div>

          {/* Quick Preset Buttons */}
          <div className="mt-4 pt-3 border-t border-gray-700">
            <p className="text-xs text-gray-500 mb-2">Try a preset scenario:</p>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => { setRevGrowthDelta(200); setOpexDelta(-100); setDiscountRateDelta(-50); }}
                className="px-3 py-1.5 bg-green-500/20 text-green-400 text-xs rounded-md hover:bg-green-500/30 transition-colors border border-green-500/30"
              >
                🚀 Optimistic
              </button>
              <button
                onClick={() => { setRevGrowthDelta(0); setOpexDelta(0); setDiscountRateDelta(0); }}
                className="px-3 py-1.5 bg-gray-600/50 text-gray-300 text-xs rounded-md hover:bg-gray-600 transition-colors border border-gray-600"
              >
                ⚖️ Baseline
              </button>
              <button
                onClick={() => { setRevGrowthDelta(-200); setOpexDelta(150); setDiscountRateDelta(100); }}
                className="px-3 py-1.5 bg-red-500/20 text-red-400 text-xs rounded-md hover:bg-red-500/30 transition-colors border border-red-500/30"
              >
                📉 Pessimistic
              </button>
              <button
                onClick={() => { setRevGrowthDelta(-300); setOpexDelta(200); setDiscountRateDelta(200); }}
                className="px-3 py-1.5 bg-orange-500/20 text-orange-400 text-xs rounded-md hover:bg-orange-500/30 transition-colors border border-orange-500/30"
              >
                ⚠️ Recession
              </button>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {/* OpEx Delta Slider */}
          <div>
            <label className="block text-sm font-medium text-white mb-2">
              OpEx Delta: <span className="text-blue-400">{opexDelta} bps</span>
              <span className="text-gray-500 text-xs ml-2">({(opexDelta / 100).toFixed(2)}%)</span>
            </label>
            <input
              type="range"
              min="-10000"
              max="10000"
              step="100"
              value={opexDelta}
              onChange={(e) => setOpexDelta(Number(e.target.value))}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Negative = Cost cutting (Higher Profit), Positive = More spending (Lower Profit)
            </p>
          </div>

          {/* Revenue Growth Delta Slider */}
          <div>
            <label className="block text-sm font-medium text-white mb-2">
              Revenue Growth Delta: <span className="text-blue-400">{revGrowthDelta} bps</span>
              <span className="text-gray-500 text-xs ml-2">({(revGrowthDelta / 100).toFixed(2)}%)</span>
            </label>
            <input
              type="range"
              min="-10000"
              max="10000"
              step="100"
              value={revGrowthDelta}
              onChange={(e) => setRevGrowthDelta(Number(e.target.value))}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Positive = Faster growth, Negative = Slower growth or decline
            </p>
          </div>

          {/* Discount Rate Delta Slider */}
          <div>
            <label className="block text-sm font-medium text-white mb-2">
              Discount Rate Delta: <span className="text-blue-400">{discountRateDelta} bps</span>
              <span className="text-gray-500 text-xs ml-2">({(discountRateDelta / 100).toFixed(2)}%)</span>
            </label>
            <input
              type="range"
              min="-10000"
              max="10000"
              step="100"
              value={discountRateDelta}
              onChange={(e) => setDiscountRateDelta(Number(e.target.value))}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Higher = Future cash worth less (Lower Valuation), Lower = Future cash worth more (Higher Valuation)
            </p>
          </div>

          {/* Submit Button */}
          <button
            onClick={handleCreateScenario}
            disabled={creating}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-medium py-3 px-6 rounded-lg transition-colors"
          >
            {creating ? 'Creating...' : '▶️ Run Simulation + Debate'}
          </button>
        </div>
      </div>
    </div>
  )
}
