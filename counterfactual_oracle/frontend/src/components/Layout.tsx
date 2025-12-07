import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
    LayoutDashboard,
    Upload,
    BarChart3,
    Activity,
    Zap,
    MessageSquare,
    Users,
    FileDown,
    Settings,
    Menu,
    X,
    HelpCircle,
    ChevronLeft
} from 'lucide-react';

interface LayoutProps {
    children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
    const location = useLocation();
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);

    const navItems = [
        { name: 'Dashboard', path: '/', icon: LayoutDashboard },
        { name: 'Upload', path: '/upload', icon: Upload },
        { name: 'Metrics', path: '/metrics', icon: Activity },
        { name: 'Simulation', path: '/simulation', icon: Zap },
        { name: 'Settings', path: '/settings', icon: Settings },
    ];

    return (
        <div className="flex h-screen bg-gray-950 text-white overflow-hidden">
            {/* Sidebar */}
            <aside
                className={`
          fixed inset-y-0 left-0 z-50 w-64 bg-gray-950 border-r border-gray-800 transition-transform duration-300 ease-in-out
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          md:relative md:translate-x-0
        `}
            >
                <div className="flex flex-col h-full">
                    {/* Logo */}
                    <div className="p-6 flex items-center gap-3">
                        <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center text-gray-950 font-bold">
                            <Zap size={20} fill="currentColor" />
                        </div>
                        <div>
                            <h1 className="font-semibold text-sm leading-tight">Counterfactual</h1>
                            <p className="text-xs text-gray-400">Oracle</p>
                        </div>
                    </div>

                    {/* Navigation */}
                    <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
                        {navItems.map((item) => {
                            const isActive = location.pathname === item.path;
                            const Icon = item.icon;

                            return (
                                <Link
                                    key={item.path}
                                    to={item.path}
                                    className={`
                    flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                    ${isActive
                                            ? 'bg-gray-800 text-white'
                                            : 'text-gray-400 hover:text-white hover:bg-gray-900'
                                        }
                  `}
                                >
                                    <Icon size={18} />
                                    <span>{item.name}</span>
                                    {item.name === 'Debate' && (
                                        <span className="ml-auto text-[10px] bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded">AI</span>
                                    )}
                                </Link>
                            );
                        })}
                    </nav>

                    {/* Bottom Actions */}
                    <div className="p-4 border-t border-gray-800 space-y-2">
                        <button className="flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-900 transition-colors">
                            <HelpCircle size={18} />
                            <span>Help & Support</span>
                        </button>
                        <button
                            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                            className="flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-900 transition-colors md:hidden"
                        >
                            <ChevronLeft size={18} />
                            <span>Collapse Sidebar</span>
                        </button>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
                {/* Mobile Header */}
                <header className="md:hidden flex items-center justify-between p-4 border-b border-gray-800 bg-gray-950">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center text-gray-950 font-bold">
                            <Zap size={20} fill="currentColor" />
                        </div>
                        <span className="font-semibold">Counterfactual Oracle</span>
                    </div>
                    <button
                        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                        className="p-2 text-gray-400 hover:text-white"
                    >
                        {isSidebarOpen ? <X size={24} /> : <Menu size={24} />}
                    </button>
                </header>

                {/* Content Area */}
                <div className="flex-1 overflow-y-auto p-4 md:p-8">
                    <div className="max-w-7xl mx-auto">
                        {children}
                    </div>
                </div>
            </main>
        </div>
    );
};

export default Layout;
