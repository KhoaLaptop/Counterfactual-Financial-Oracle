import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';
import Home from './pages/Home'; // Keeping old Home as Upload page for now, or we can rename/refactor
import ReportPage from './pages/ReportPage';
import ScenarioPage from './pages/ScenarioPage';

import ReportList from './pages/ReportList';
import ScenarioList from './pages/ScenarioList';

// Placeholder components for new routes
const Placeholder = ({ title }: { title: string }) => (
  <div className="flex flex-col items-center justify-center h-[60vh] text-gray-400">
    <h2 className="text-xl font-medium mb-2">{title}</h2>
    <p>This feature is coming soon.</p>
  </div>
);

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/upload" element={<Home />} /> {/* Reusing old Home logic for Upload */}
        <Route path="/settings" element={<Settings />} />

        {/* Existing Routes */}
        <Route path="/reports/:reportId" element={<ReportPage />} />
        <Route path="/scenarios/:scenarioId" element={<ScenarioPage />} />

        {/* List Pages */}
        <Route path="/overview" element={<ReportList />} />
        <Route path="/metrics" element={<ReportList />} />

        <Route path="/simulation" element={<ScenarioList />} />
        <Route path="/critique" element={<ScenarioList />} />
        <Route path="/debate" element={<ScenarioList />} />
        <Route path="/scenarios" element={<ScenarioList />} />
        <Route path="/export" element={<ScenarioList />} />
      </Routes>
    </Layout>
  );
}

export default App;
