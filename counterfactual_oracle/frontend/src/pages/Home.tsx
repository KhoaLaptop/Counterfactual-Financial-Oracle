import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { reportsApi } from '../lib/api'
import { Upload, FileText, Sparkles, BarChart3, Shield, MessageSquare, Calculator, FileOutput } from 'lucide-react'

export default function Home() {
  const navigate = useNavigate()
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const pdfInputRef = useRef<HTMLInputElement>(null)
  const jsonInputRef = useRef<HTMLInputElement>(null)

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)

    try {
      const report = await reportsApi.upload(file, null)
      navigate(`/reports/${report.id}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload report')
    } finally {
      setUploading(false)
    }
  }

  const handleJsonUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)

    try {
      const text = await file.text()
      const report = await reportsApi.upload(null, text)
      navigate(`/reports/${report.id}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload report')
    } finally {
      setUploading(false)
    }
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    const file = e.dataTransfer.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)

    try {
      if (file.name.endsWith('.json')) {
        const text = await file.text()
        const report = await reportsApi.upload(null, text)
        navigate(`/reports/${report.id}`)
      } else {
        const report = await reportsApi.upload(file, null)
        navigate(`/reports/${report.id}`)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload report')
    } finally {
      setUploading(false)
    }
  }

  const features = [
    { icon: Sparkles, label: 'AI-powered document extraction', desc: 'Landing AI' },
    { icon: BarChart3, label: 'Monte Carlo simulation', desc: '10,000 scenarios' },
    { icon: Shield, label: 'Adversarial critique', desc: 'DeepSeek Reasoner' },
    { icon: MessageSquare, label: 'Multi-agent debate', desc: 'Gemini vs DeepSeek' },
    { icon: Calculator, label: 'DCF valuation', desc: 'Gordon Growth model' },
    { icon: FileOutput, label: 'PDF report generation', desc: 'Professional exports' },
  ]

  return (
    <div className="space-y-8">
      {/* Hero Header */}
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-pink-500 mb-4">
          <span className="text-3xl">🔮</span>
        </div>
        <h1 className="text-3xl font-bold text-white mb-2">
          Counterfactual Financial Oracle
        </h1>
        <p className="text-gray-400 max-w-lg mx-auto">
          Multi-agent AI system for counterfactual financial analysis with Monte Carlo simulation and adversarial debate
        </p>
      </div>

      {/* Upload Section */}
      <div className="bg-gradient-to-br from-gray-900 to-gray-800 border border-gray-700 rounded-2xl p-8">
        <h2 className="text-xl font-semibold text-white mb-6 text-center">Upload Financial Report</h2>

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-center">
            {error}
          </div>
        )}

        {/* Drag & Drop Zone */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${dragActive
              ? 'border-blue-500 bg-blue-500/10'
              : 'border-gray-600 hover:border-gray-500 hover:bg-gray-800/50'
            }`}
          onClick={() => pdfInputRef.current?.click()}
        >
          {uploading ? (
            <div className="flex flex-col items-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mb-4"></div>
              <p className="text-gray-400">Processing document...</p>
              <p className="text-xs text-gray-500 mt-1">This may take a few seconds</p>
            </div>
          ) : (
            <>
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-800 mb-4">
                <Upload className="w-8 h-8 text-blue-400" />
              </div>
              <p className="text-white font-medium mb-1">
                Drag & drop your PDF here
              </p>
              <p className="text-gray-500 text-sm mb-4">
                or click to browse
              </p>
              <p className="text-xs text-gray-600">
                Supports 10-K, 10-Q, and Annual Reports
              </p>
            </>
          )}
          <input
            ref={pdfInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileUpload}
            disabled={uploading}
            className="hidden"
          />
        </div>

        {/* Alternative JSON Upload */}
        <div className="mt-6 pt-6 border-t border-gray-700">
          <div className="flex items-center justify-center gap-4">
            <span className="text-gray-500 text-sm">or upload pre-extracted data</span>
            <button
              onClick={() => jsonInputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors text-sm"
            >
              <FileText className="w-4 h-4" />
              Upload JSON
            </button>
            <input
              ref={jsonInputRef}
              type="file"
              accept=".json"
              onChange={handleJsonUpload}
              disabled={uploading}
              className="hidden"
            />
          </div>
        </div>
      </div>

      {/* Features Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {features.map((feature, idx) => (
          <div
            key={idx}
            className="bg-gray-900/50 border border-gray-800 rounded-xl p-4 hover:bg-gray-800/50 transition-colors"
          >
            <feature.icon className="w-6 h-6 text-blue-400 mb-3" />
            <p className="text-white text-sm font-medium mb-1">{feature.label}</p>
            <p className="text-gray-500 text-xs">{feature.desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
