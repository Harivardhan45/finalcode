import React, { useState } from 'react';
import AIPoweredSearch from './components/AIPoweredSearch';
import VideoSummarizer from './components/VideoSummarizer';
import CodeAssistant from './components/CodeAssistant';
import ImpactAnalyzer from './components/ImpactAnalyzer';
import TestSupportTool from './components/TestSupportTool';
import ImageInsights from './components/ImageInsights';
import CircularLauncher from './components/CircularLauncher';

export type FeatureType = 'search' | 'video' | 'code' | 'impact' | 'test' | 'image' | null;

function App() {
  const [activeFeature, setActiveFeature] = useState<FeatureType>(null);
  const [isAppOpen, setIsAppOpen] = useState(false);

  const renderActiveFeature = () => {
    switch (activeFeature) {
      case 'search':
        return <AIPoweredSearch onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} />;
      case 'video':
        return <VideoSummarizer onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} />;
      case 'code':
        return <CodeAssistant onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} />;
      case 'impact':
        return <ImpactAnalyzer onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} />;
      case 'test':
        return <TestSupportTool onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} />;
      case 'image':
        return <ImageInsights onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} />;
      default:
        return <AIPoweredSearch onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} />;
    }
  };

  const handleLauncherClick = () => {
    setIsAppOpen(true);
    setActiveFeature('search');
  };

  const handleAppClose = () => {
    setIsAppOpen(false);
    setActiveFeature(null);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      {!isAppOpen && (
        <CircularLauncher onClick={handleLauncherClick} />
      )}
      
      {isAppOpen && (
        <div>
          {activeFeature ? (
            renderActiveFeature()
          ) : (
            <AIPoweredSearch onClose={handleAppClose} onFeatureSelect={setActiveFeature} />
          )}
        </div>
      )}
    </div>
  );
}

export default App;