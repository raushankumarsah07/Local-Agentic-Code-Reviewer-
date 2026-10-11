import React, { useState } from 'react';
import Navbar from './components/Navbar';
import ProjectsList from './components/ProjectsList';
import UploadModal from './components/UploadModal';
import ProjectDashboard from './components/ProjectDashboard';

function App() {
  // Navigation views: 'projects' | 'upload' | 'dashboard'
  const [currentView, setCurrentView] = useState('projects');
  const [selectedProjectId, setSelectedProjectId] = useState(null);

  // When a user selects a project from the projects list
  const handleSelectProject = (projectOrId) => {
    const id = typeof projectOrId === 'object' && projectOrId !== null
      ? (projectOrId.project_id || projectOrId.id)
      : projectOrId;
    setSelectedProjectId(id);
    setCurrentView('dashboard');
  };

  // When a ZIP archive is successfully uploaded and extracted
  const handleUploadSuccess = (uploadResult) => {
    setSelectedProjectId(uploadResult.project_id);
    setCurrentView('dashboard');
  };

  // Switch navigation tabs from Navbar
  const handleNavChange = (view) => {
    setCurrentView(view);
    if (view !== 'dashboard') {
      setSelectedProjectId(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-brand-500/30 selection:text-white">
      {/* Top Global Navigation Bar */}
      <Navbar
        activeTab={currentView}
        setActiveTab={handleNavChange}
      />

      {/* Main App Body */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {currentView === 'projects' && (
          <ProjectsList
            onSelectProject={handleSelectProject}
            onNavigateUpload={() => setCurrentView('upload')}
          />
        )}

        {currentView === 'upload' && (
          <UploadModal
            onUploadSuccess={handleUploadSuccess}
            onCancel={() => setCurrentView('projects')}
          />
        )}

        {currentView === 'dashboard' && selectedProjectId && (
          <ProjectDashboard
            projectId={selectedProjectId}
            onBack={() => {
              setCurrentView('projects');
              setSelectedProjectId(null);
            }}
          />
        )}
      </main>
    </div>
  );
}

export default App;
