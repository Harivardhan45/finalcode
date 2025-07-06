import React, { useState, useEffect } from 'react';
import AIPoweredSearch from './components/AIPoweredSearch';
import VideoSummarizer from './components/VideoSummarizer';
import CodeAssistant from './components/CodeAssistant';
import ImpactAnalyzer from './components/ImpactAnalyzer';
import TestSupportTool from './components/TestSupportTool';
import ImageInsights from './components/ImageInsights';
import CircularLauncher from './components/CircularLauncher';
import { getSpaceKeyFromURL, isSpaceConnected } from './utils/urlUtils';

export type FeatureType = 'search' | 'video' | 'code' | 'impact' | 'test' | 'image' | null;

function App() {
  const [activeFeature, setActiveFeature] = useState<FeatureType>(null);
  const [isAppOpen, setIsAppOpen] = useState(false);
  const [autoSpaceKey, setAutoSpaceKey] = useState<string | null>(null);
  const [isSpaceAutoConnected, setIsSpaceAutoConnected] = useState(false);

  useEffect(() => {
    const spaceKey = getSpaceKeyFromURL();
    if (spaceKey) {
      setAutoSpaceKey(spaceKey);
      setIsSpaceAutoConnected(true);
    }
  }, []);

  const renderActiveFeature = () => {
    const commonProps = {
      autoSpaceKey,
      isSpaceAutoConnected,
      onClose: () => setActiveFeature(null),
      onFeatureSelect: setActiveFeature
    };

    switch (activeFeature) {
      case 'search':
        return <AIPoweredSearch {...commonProps} />;
      case 'video':
        return <VideoSummarizer {...commonProps} />;
      case 'code':
        return <CodeAssistant {...commonProps} />;
      case 'impact':
        return <ImpactAnalyzer {...commonProps} />;
      case 'test':
        return <TestSupportTool {...commonProps} />;
      case 'image':
        return <ImageInsights {...commonProps} />;
      default:
        return <AIPoweredSearch {...commonProps} />;
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
            <AIPoweredSearch 
              autoSpaceKey={autoSpaceKey}
              isSpaceAutoConnected={isSpaceAutoConnected}
              onClose={handleAppClose} 
              onFeatureSelect={setActiveFeature} 
            />
          )}
        </div>
      )}
    </div>
  );
}

export default App;