import React from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reportsApi } from '../lib/api'
import { Link, useNavigate } from 'react-router-dom'
import { FileText, Calendar, Upload, Trash2 } from 'lucide-react'
import { ReportSummary } from '../lib/types'

export default function ReportList() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: reports, isLoading } = useQuery<ReportSummary[]>({
    queryKey: ['reports'],
    queryFn: () => reportsApi.list(),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => reportsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
    onError: (error: any) => {
      alert('Failed to delete report: ' + (error.response?.data?.detail || error.message))
    }
  })

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.preventDefault() // Prevent navigation
    if (window.confirm('Are you sure you want to delete this report?')) {
      deleteMutation.mutate(id)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950 py-8">
      <div className="container mx-auto px-4 max-w-6xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Financial Reports</h1>
            <p className="text-gray-400">Select a report to view analysis and metrics</p>
          </div>
          <button
            onClick={() => navigate('/upload')}
            className="btn-primary flex items-center gap-2"
          >
            <Upload size={18} />
            Upload New Report
          </button>
        </div>

        <div className="space-y-4">
          {reports?.map((report) => (
            <Link
              key={report.id}
              to={`/reports/${report.id}`}
              className="block bg-gray-900 rounded-xl p-6 border border-gray-800 hover:border-blue-500/50 transition-all group relative"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-gray-800 rounded-lg group-hover:bg-blue-500/10 group-hover:text-blue-400 transition-colors">
                    <FileText size={24} />
                  </div>
                  <div>
                    <h3 className="font-medium text-lg text-white mb-1">
                      {report.company_name || report.pdf_metadata?.filename || 'Untitled Report'}
                    </h3>
                    <div className="flex items-center gap-4 text-sm text-gray-400">
                      <span className="flex items-center gap-1">
                        <Calendar size={14} />
                        FY {report.fiscal_year || 'N/A'}
                      </span>
                      <span>
                        Uploaded {new Date(report.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <button
                    onClick={(e) => handleDelete(e, report.id)}
                    className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors z-10"
                    title="Delete Report"
                  >
                    <Trash2 size={20} />
                  </button>
                  <div className="text-gray-600 group-hover:text-blue-400 transition-colors">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </div>
            </Link>
          ))}

          {reports?.length === 0 && (
            <div className="text-center py-12 bg-gray-900 rounded-xl border border-gray-800 border-dashed">
              <FileText className="mx-auto h-12 w-12 text-gray-600 mb-4" />
              <h3 className="text-lg font-medium text-white mb-2">No reports found</h3>
              <p className="text-gray-400 mb-6">Upload a financial report to get started</p>
              <button
                onClick={() => navigate('/upload')}
                className="btn-primary"
              >
                Upload Report
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
