import React, { useState, useEffect } from 'react';
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
  const [autoSpaceKey, setAutoSpaceKey] = useState<string | null>(null);
  const [isSpaceAutoConnected, setIsSpaceAutoConnected] = useState(false);

  // Extract space key from URL on component mount
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const spaceKey = urlParams.get('space');
    if (spaceKey) {
      setAutoSpaceKey(spaceKey);
      setIsSpaceAutoConnected(true);
    }
  }, []);

  const renderActiveFeature = () => {
    switch (activeFeature) {
      case 'search':
        return <AIPoweredSearch onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} autoSpaceKey={autoSpaceKey} isSpaceAutoConnected={isSpaceAutoConnected} />;
      case 'video':
        return <VideoSummarizer onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} autoSpaceKey={autoSpaceKey} isSpaceAutoConnected={isSpaceAutoConnected} />;
      case 'code':
        return <CodeAssistant onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} autoSpaceKey={autoSpaceKey} isSpaceAutoConnected={isSpaceAutoConnected} />;
      case 'impact':
        return <ImpactAnalyzer onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} autoSpaceKey={autoSpaceKey} isSpaceAutoConnected={isSpaceAutoConnected} />;
      case 'test':
        return <TestSupportTool onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} autoSpaceKey={autoSpaceKey} isSpaceAutoConnected={isSpaceAutoConnected} />;
      case 'image':
        return <ImageInsights onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} autoSpaceKey={autoSpaceKey} isSpaceAutoConnected={isSpaceAutoConnected} />;
      default:
        return <AIPoweredSearch onClose={() => setActiveFeature(null)} onFeatureSelect={setActiveFeature} autoSpaceKey={autoSpaceKey} isSpaceAutoConnected={isSpaceAutoConnected} />;
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
            <AIPoweredSearch onClose={handleAppClose} onFeatureSelect={setActiveFeature} autoSpaceKey={autoSpaceKey} isSpaceAutoConnected={isSpaceAutoConnected} />
          )}
        </div>
      )}
    </div>
  );
}

export default App;