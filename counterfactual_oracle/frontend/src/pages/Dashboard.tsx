import React from 'react';
import { Upload, BarChart3, Zap, MessageSquare, Users, FileDown } from 'lucide-react';
import { Link } from 'react-router-dom';

const Dashboard: React.FC = () => {
    console.log('Dashboard mounted')
    const features = [
        {
            icon: Upload,
            title: 'PDF Extraction',
            description: 'Upload financial documents and extract key metrics using AI-powered OCR',
            path: '/upload'
        },
        {
            icon: BarChart3,
            title: 'Financial Analysis',
            description: 'Comprehensive analysis of profitability, leverage, liquidity, and efficiency metrics',
            path: '/metrics'
        },
        {
            icon: Zap,
            title: 'Monte Carlo Simulation',
            description: 'Run thousands of scenarios to understand risk and forecast outcomes',
            path: '/simulation'
        },
        {
            icon: MessageSquare,
            title: 'Adversarial Critique',
            description: 'AI-powered validation to identify assumptions and potential risks',
            path: '/critique'
        },
        {
            icon: Users,
            title: 'AI Debate',
            description: 'Watch AI agents debate investment merits to reach consensus verdicts',
            path: '/debate'
        },
        {
            icon: FileDown,
            title: 'Scenario Analysis',
            description: 'Test optimistic, base case, and conservative scenarios side-by-side',
            path: '/scenarios'
        }
    ];

    return (
        <div className="space-y-8">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-semibold mb-1">Counterfactual Financial Oracle</h1>
                <p className="text-gray-400">AI-powered financial analysis with adversarial validation and multi-agent debate</p>
            </div>

            {/* Quick Start Guide */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <h2 className="text-lg font-medium mb-4">Quick Start Guide</h2>
                <p className="text-gray-400 mb-6">Get started with your financial analysis in three simple steps</p>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    <div className="flex items-start gap-4">
                        <div className="w-8 h-8 rounded-full bg-white text-gray-950 flex items-center justify-center font-bold shrink-0">1</div>
                        <div>
                            <h3 className="font-medium mb-1">Upload Documents</h3>
                            <p className="text-sm text-gray-400">Upload financial PDFs or JSON data files</p>
                        </div>
                    </div>

                    <div className="flex items-start gap-4">
                        <div className="w-8 h-8 rounded-full bg-white text-gray-950 flex items-center justify-center font-bold shrink-0">2</div>
                        <div>
                            <h3 className="font-medium mb-1">Review Metrics</h3>
                            <p className="text-sm text-gray-400">Examine extracted financial data and key ratios</p>
                        </div>
                    </div>

                    <div className="flex items-start gap-4">
                        <div className="w-8 h-8 rounded-full bg-white text-gray-950 flex items-center justify-center font-bold shrink-0">3</div>
                        <div>
                            <h3 className="font-medium mb-1">Run Analysis</h3>
                            <p className="text-sm text-gray-400">Simulate scenarios and get AI-validated insights</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Features Grid */}
            <div>
                <h2 className="text-lg font-medium mb-4">Features</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {features.map((feature, index) => {
                        const Icon = feature.icon;
                        return (
                            <Link
                                key={index}
                                to={feature.path}
                                className="bg-gray-900 border border-gray-800 rounded-xl p-6 hover:bg-gray-800 transition-colors group"
                            >
                                <div className="w-10 h-10 bg-gray-800 rounded-lg flex items-center justify-center mb-4 group-hover:bg-gray-700 transition-colors">
                                    <Icon size={20} className="text-gray-200" />
                                </div>
                                <h3 className="font-medium mb-2">{feature.title}</h3>
                                <p className="text-sm text-gray-400 leading-relaxed">{feature.description}</p>
                            </Link>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
