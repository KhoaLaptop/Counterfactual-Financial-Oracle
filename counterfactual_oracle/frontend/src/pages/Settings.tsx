import React, { useState } from 'react';
import { Save, Key, Moon, Sliders, Database } from 'lucide-react';

const Settings: React.FC = () => {
    const [apiKeys, setApiKeys] = useState({
        landingAi: '',
        openAi: '',
        deepSeek: ''
    });

    const [simulationDefaults, setSimulationDefaults] = useState({
        iterations: 10000,
        discountRate: 10
    });

    const [darkMode, setDarkMode] = useState(true);

    return (
        <div className="space-y-8 max-w-4xl">
            <div>
                <h1 className="text-2xl font-semibold mb-1">Settings</h1>
                <p className="text-gray-400">Configure API keys, preferences, and application settings</p>
            </div>

            {/* API Configuration */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <div className="flex items-center gap-2 mb-6">
                    <Key size={20} className="text-gray-400" />
                    <h2 className="text-lg font-medium">API Configuration</h2>
                </div>
                <p className="text-sm text-gray-400 mb-6">Configure API keys for external services. Keys are stored locally in your browser.</p>

                <div className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium mb-2">Landing AI API Key</label>
                        <input
                            type="password"
                            placeholder="Enter your Landing AI API key"
                            className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-gray-600 transition-colors"
                            value={apiKeys.landingAi}
                            onChange={(e) => setApiKeys({ ...apiKeys, landingAi: e.target.value })}
                        />
                        <p className="text-xs text-gray-500 mt-1.5">Used for PDF extraction and OCR processing</p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium mb-2">OpenAI API Key</label>
                        <input
                            type="password"
                            placeholder="Enter your OpenAI API key"
                            className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-gray-600 transition-colors"
                            value={apiKeys.openAi}
                            onChange={(e) => setApiKeys({ ...apiKeys, openAi: e.target.value })}
                        />
                        <p className="text-xs text-gray-500 mt-1.5">Powers the AI debate and analysis features</p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium mb-2">DeepSeek API Key (Optional)</label>
                        <input
                            type="password"
                            placeholder="Enter your DeepSeek API key"
                            className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-gray-600 transition-colors"
                            value={apiKeys.deepSeek}
                            onChange={(e) => setApiKeys({ ...apiKeys, deepSeek: e.target.value })}
                        />
                        <p className="text-xs text-gray-500 mt-1.5">Alternative AI model for cost optimization</p>
                    </div>

                    <button className="w-full bg-white text-gray-950 font-medium py-2.5 rounded-lg hover:bg-gray-100 transition-colors flex items-center justify-center gap-2">
                        <Save size={18} />
                        <span>Save API Keys</span>
                    </button>
                </div>
            </div>

            {/* Appearance */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <div className="flex items-center gap-2 mb-6">
                    <Moon size={20} className="text-gray-400" />
                    <h2 className="text-lg font-medium">Appearance</h2>
                </div>
                <p className="text-sm text-gray-400 mb-6">Customize the look and feel of the application</p>

                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-sm font-medium">Dark Mode</h3>
                        <p className="text-xs text-gray-500 mt-0.5">Toggle between light and dark theme</p>
                    </div>
                    <button
                        onClick={() => setDarkMode(!darkMode)}
                        className={`w-11 h-6 rounded-full transition-colors relative ${darkMode ? 'bg-white' : 'bg-gray-700'}`}
                    >
                        <div className={`w-4 h-4 rounded-full bg-gray-950 absolute top-1 transition-transform ${darkMode ? 'left-6' : 'left-1'}`} />
                    </button>
                </div>
            </div>

            {/* Simulation Defaults */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <div className="flex items-center gap-2 mb-6">
                    <Sliders size={20} className="text-gray-400" />
                    <h2 className="text-lg font-medium">Simulation Defaults</h2>
                </div>
                <p className="text-sm text-gray-400 mb-6">Set default parameters for Monte Carlo simulations</p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    <div>
                        <label className="block text-sm font-medium mb-2">Iterations</label>
                        <input
                            type="number"
                            className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-gray-600 transition-colors"
                            value={simulationDefaults.iterations}
                            onChange={(e) => setSimulationDefaults({ ...simulationDefaults, iterations: parseInt(e.target.value) })}
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-2">Default Discount Rate (%)</label>
                        <input
                            type="number"
                            className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-gray-600 transition-colors"
                            value={simulationDefaults.discountRate}
                            onChange={(e) => setSimulationDefaults({ ...simulationDefaults, discountRate: parseInt(e.target.value) })}
                        />
                    </div>
                </div>

                <button className="w-full bg-gray-800 text-gray-300 font-medium py-2.5 rounded-lg hover:bg-gray-700 transition-colors">
                    Reset to Defaults
                </button>
            </div>

            {/* Data Management */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <div className="flex items-center gap-2 mb-6">
                    <Database size={20} className="text-gray-400" />
                    <h2 className="text-lg font-medium">Data Management</h2>
                </div>
                <p className="text-sm text-gray-400 mb-6">Manage your local data and analysis history</p>

                <div className="space-y-3">
                    <button className="w-full bg-gray-800 text-gray-300 font-medium py-2.5 rounded-lg hover:bg-gray-700 transition-colors">
                        Clear Analysis History
                    </button>
                    <button className="w-full bg-red-900/20 text-red-400 border border-red-900/50 font-medium py-2.5 rounded-lg hover:bg-red-900/30 transition-colors">
                        Clear All Data & Reset
                    </button>
                </div>
            </div>
        </div>
    );
};

export default Settings;
