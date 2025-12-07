import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { scenariosApi } from '../lib/api';
import { Zap, ChevronRight, Clock, AlertCircle, CheckCircle } from 'lucide-react';

const ScenarioList: React.FC = () => {
    const { data: scenarios, isLoading } = useQuery({
        queryKey: ['scenarios'],
        queryFn: scenariosApi.list,
    });

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'COMPLETED': return 'text-green-400 bg-green-900/20 border-green-900/50';
            case 'FAILED': return 'text-red-400 bg-red-900/20 border-red-900/50';
            case 'RUNNING': return 'text-yellow-400 bg-yellow-900/20 border-yellow-900/50';
            default: return 'text-gray-400 bg-gray-800 border-gray-700';
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'COMPLETED': return <CheckCircle size={14} />;
            case 'FAILED': return <AlertCircle size={14} />;
            default: return <Clock size={14} />;
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-semibold mb-1">Scenario Analysis</h1>
                    <p className="text-gray-400">View and analyze your financial simulations</p>
                </div>
                <Link
                    to="/upload"
                    className="bg-white text-gray-950 px-4 py-2 rounded-lg font-medium hover:bg-gray-100 transition-colors"
                >
                    New Scenario
                </Link>
            </div>

            <div className="grid gap-4">
                {scenarios?.map((scenario) => (
                    <Link
                        key={scenario.id}
                        to={`/scenarios/${scenario.id}`}
                        className="bg-gray-900 border border-gray-800 rounded-xl p-6 hover:bg-gray-800 transition-colors flex items-center justify-between group"
                    >
                        <div className="flex items-center gap-4">
                            <div className="w-12 h-12 bg-gray-800 rounded-lg flex items-center justify-center group-hover:bg-gray-700 transition-colors">
                                <Zap size={24} className="text-gray-400 group-hover:text-white" />
                            </div>
                            <div>
                                <h3 className="font-medium text-lg text-white mb-1">
                                    {scenario.name || 'Untitled Scenario'}
                                </h3>
                                <div className="flex items-center gap-4 text-sm">
                                    <span className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${getStatusColor(scenario.status)}`}>
                                        {getStatusIcon(scenario.status)}
                                        {scenario.status}
                                    </span>
                                    <span className="text-gray-400">
                                        Created {new Date(scenario.created_at).toLocaleDateString()}
                                    </span>
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center gap-6">
                            {scenario.status === 'COMPLETED' && scenario.final_verdict && (
                                <div className="text-right hidden md:block">
                                    <p className="text-xs text-gray-500 mb-0.5">Verdict</p>
                                    <p className="font-medium text-white">{scenario.final_verdict}</p>
                                </div>
                            )}
                            <ChevronRight size={20} className="text-gray-600 group-hover:text-white transition-colors" />
                        </div>
                    </Link>
                ))}

                {scenarios?.length === 0 && (
                    <div className="text-center py-12 bg-gray-900 border border-gray-800 rounded-xl">
                        <Zap size={48} className="mx-auto text-gray-700 mb-4" />
                        <h3 className="text-lg font-medium text-gray-300 mb-2">No scenarios found</h3>
                        <p className="text-gray-500 mb-6">Create a scenario from a report to get started</p>
                        <Link
                            to="/upload"
                            className="text-blue-400 hover:text-blue-300 font-medium"
                        >
                            Go to Uploads →
                        </Link>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ScenarioList;
