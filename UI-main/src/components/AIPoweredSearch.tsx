import React, { useState, useEffect } from 'react';
import { Search, Download, Save, FileText, X, ChevronDown, Loader2, Settings, Video, Code, TrendingUp, TestTube, Image, CheckCircle, ChevronUp } from 'lucide-react';
import { FeatureType, AppMode } from '../App';
import { apiService, Space } from '../services/api';
import CustomScrollbar from './CustomScrollbar';
import { getConfluenceSpaceAndPageFromUrl } from '../utils/urlUtils';

interface AIPoweredSearchProps {
  onClose: () => void;
  onFeatureSelect: (feature: FeatureType) => void;
  onModeSelect: (mode: AppMode) => void;
  autoSpaceKey?: string | null;
  isSpaceAutoConnected?: boolean;
}

const AIPoweredSearch: React.FC<AIPoweredSearchProps> = ({ 
  onClose, 
  onFeatureSelect, 
  onModeSelect,
  autoSpaceKey, 
  isSpaceAutoConnected 
}) => {
  const [selectedSpace, setSelectedSpace] = useState('');
  const [selectedPages, setSelectedPages] = useState<string[]>([]);
  const [isPageDropdownOpen, setIsPageDropdownOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showRawContent, setShowRawContent] = useState(false);
  const [exportFormat, setExportFormat] = useState('markdown');
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [pages, setPages] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [showToast, setShowToast] = useState(false);

  const toggleSelectAllPages = () => {
    if (selectedPages.length === pages.length) {
      setSelectedPages([]);
    } else {
      setSelectedPages([...pages]);
    } 
  };

  const handlePageSelection = (page: string) => {
    setSelectedPages(prev =>
      prev.includes(page)
        ? prev.filter(p => p !== page)
        : [...prev, page]
    );
  };
  const selectAllPages = () => {
    setSelectedPages(pages);
  };
  const clearAllPages = () => {
    setSelectedPages([]);
  };

  const features = [
    { id: 'search' as const, label: 'AI Powered Search', icon: Search },
    { id: 'video' as const, label: 'Video Summarizer', icon: Video },
    { id: 'code' as const, label: 'Code Assistant', icon: Code },
    { id: 'impact' as const, label: 'Impact Analyzer', icon: TrendingUp },
    { id: 'test' as const, label: 'Test Support Tool', icon: TestTube },
    { id: 'image' as const, label: 'Image Insights & Chart Builder', icon: Image },
  ];

  // Load spaces on component mount
  useEffect(() => {
    loadSpaces();
  }, []);

  // Auto-select space if provided via URL
  useEffect(() => {
    if (autoSpaceKey && isSpaceAutoConnected) {
      setSelectedSpace(autoSpaceKey);
    }
  }, [autoSpaceKey, isSpaceAutoConnected]);

  // Load pages when space is selected
  useEffect(() => {
    if (selectedSpace) {
      loadPages();
    }
  }, [selectedSpace]);

  // Sync "Select All" checkbox state

  // Only auto-select page from URL if no page is already selected
  useEffect(() => {
    if (pages.length > 0 && selectedPages.length === 0) {
      const { page } = getConfluenceSpaceAndPageFromUrl();
      if (page && pages.includes(page)) {
        setSelectedPages([page]);
      }
    }
  }, [pages, selectedPages]);

  const loadSpaces = async () => {
    try {
      setError('');
      const result = await apiService.getSpaces();
      setSpaces(result.spaces);
    } catch (err) {
      setError('Failed to load spaces. Please check your backend connection.');
      console.error('Error loading spaces:', err);
    }
  };

  const loadPages = async () => {
    try {
      setError('');
      const result = await apiService.getPages(selectedSpace);
      setPages(result.pages);
      // Auto-select page if present in URL
      const { page } = getConfluenceSpaceAndPageFromUrl();
      if (page && result.pages.includes(page)) {
        setSelectedPages([page]);
      }
    } catch (err) {
      setError('Failed to load pages. Please check your space key.');
      console.error('Error loading pages:', err);
    }
  };

  const handleSearch = async () => {
    if (!selectedSpace || selectedPages.length === 0 || !query.trim()) {
      setError('Please fill in all required fields.');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const result = await apiService.search({
        space_key: selectedSpace,
        page_titles: selectedPages,
        query: query
      });

      setResponse(result.response);
    } catch (err) {
      setError('Failed to generate AI response. Please try again.');
      console.error('Error generating response:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const exportResponse = async (format: string) => {
    if (!response) return;

    try {
      const blob = await apiService.exportContent({
        content: response,
        format: format,
        filename: 'ai-search-response'
      });
      
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ai-search-response.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to export file. Please try again.');
      console.error('Error exporting:', err);
    }
  };

  return (
    <div className="fixed inset-0 bg-white flex items-center justify-center z-40 p-4">
      <div className="bg-white/80 backdrop-blur-xl border-2 border-[#DFE1E6] rounded-2xl w-full max-w-7xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-confluence-blue/90 to-confluence-light-blue/90 backdrop-blur-xl p-6 text-white border-b border-white/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Search className="w-8 h-8" />
              <div>
                <h2 className="text-2xl font-bold">Confluence AI Assistant</h2>
                <p className="text-blue-100/90">AI-powered tools for your Confluence workspace</p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <button 
                onClick={() => onModeSelect('agent')}
                className="text-blue-100 hover:text-white hover:bg-white/10 rounded-lg px-3 py-1 text-sm transition-colors"
              >
                Switch to Agent Mode
              </button>
              <button onClick={onClose} className="text-white hover:bg-white/10 rounded-full p-2 backdrop-blur-sm">
                <X className="w-6 h-6" />
              </button>
            </div>
          </div>
          
          {/* Feature Navigation */}
          <div className="mt-6 relative">
            <CustomScrollbar className="pb-2">
              <div className="flex gap-2">
                {features.map((feature) => {
                  const Icon = feature.icon;
                  const isActive = feature.id === 'search';
                  
                  return (
                    <button
                      key={feature.id}
                      onClick={() => onFeatureSelect(feature.id)}
                      className={`flex items-center space-x-2 px-4 py-2 rounded-lg backdrop-blur-sm border transition-all duration-200 whitespace-nowrap flex-shrink-0 ${
                        isActive
                          ? 'bg-white/90 text-confluence-blue shadow-lg border-white/30'
                          : 'bg-white/10 text-white hover:bg-white/20 border-white/10'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span className="text-sm font-medium">{feature.label}</span>
                    </button>
                  );
                })}
              </div>
            </CustomScrollbar>
          </div>
        </div>

        <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
          {error && (
            <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Column - Search Configuration */}
            <div className="space-y-6">
              <div className="bg-white/60 backdrop-blur-xl rounded-xl p-4 border border-white/20 shadow-lg">
                <h3 className="font-semibold text-gray-800 mb-4 flex items-center">
                  <Settings className="w-5 h-5 mr-2" />
                  Search Configuration
                </h3>
                
                {/* Space Selection */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Select Confluence Space
                  </label>
                  <div className="relative">
                    <select
                      value={selectedSpace}
                      onChange={(e) => setSelectedSpace(e.target.value)}
                      className="w-full p-3 border border-white/30 rounded-lg focus:ring-2 focus:ring-confluence-blue focus:border-confluence-blue appearance-none bg-white/70 backdrop-blur-sm"
                    >
                      <option value="">Choose a space...</option>
                      {spaces.map(space => (
                        <option key={space.key} value={space.key}>{space.name} ({space.key})</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                  </div>
                </div>

                {/* Page Selection - Aesthetic Multiselect */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Select Pages to Analyze ({selectedPages.length} selected)
                  </label>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setIsPageDropdownOpen(!isPageDropdownOpen)}
                      disabled={!selectedSpace}
                      className="w-full p-3 border border-white/30 rounded-lg focus:ring-2 focus:ring-confluence-blue focus:border-confluence-blue bg-white/70 backdrop-blur-sm text-left flex items-center justify-between disabled:bg-gray-100 disabled:cursor-not-allowed"
                    >
                      <span className={selectedPages.length === 0 ? 'text-gray-500' : 'text-gray-700'}>
                        {selectedPages.length === 0
                          ? 'Choose pages...'
                          : selectedPages.length === 1
                            ? selectedPages[0]
                            : `${selectedPages.length} pages selected`
                        }
                      </span>
                      {isPageDropdownOpen ? (
                        <ChevronUp className="w-5 h-5 text-gray-400" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-gray-400" />
                      )}
                    </button>
                    {/* Dropdown */}
                    {isPageDropdownOpen && selectedSpace && (
                      <div className="absolute z-10 w-full mt-1 bg-white/95 backdrop-blur-xl border border-white/30 rounded-lg shadow-xl max-h-60 overflow-hidden">
                        {/* Header with Select All/Clear All */}
                        <div className="p-3 border-b border-white/20 bg-white/50">
                          <div className="flex justify-between items-center">
                            <button
                              onClick={selectAllPages}
                              className="text-sm text-confluence-blue hover:text-confluence-blue/80 font-medium"
                            >
                              Select All
                            </button>
                            <button
                              onClick={clearAllPages}
                              className="text-sm text-gray-500 hover:text-gray-700 font-medium"
                            >
                              Clear All
                            </button>
                          </div>
                        </div>
                        {/* Page List */}
                        <div className="max-h-48 overflow-y-auto">
                          {pages.length === 0 ? (
                            <div className="p-3 text-gray-500 text-sm text-center">
                              No pages found in this space
                            </div>
                          ) : (
                            pages.map(page => (
                              <label
                                key={page}
                                className="flex items-center space-x-3 p-3 hover:bg-white/50 cursor-pointer border-b border-white/10 last:border-b-0"
                              >
                                <div className="relative">
                                  <input
                                    type="checkbox"
                                    checked={selectedPages.includes(page)}
                                    onChange={() => handlePageSelection(page)}
                                    className="sr-only"
                                  />
                                  <div className={`w-5 h-5 border-2 rounded flex items-center justify-center transition-colors ${
                                    selectedPages.includes(page)
                                      ? 'bg-confluence-blue border-confluence-blue'
                                      : 'border-gray-300 hover:border-confluence-blue/50'
                                  }`}>
                                    {selectedPages.includes(page) && (
                                      <CheckCircle className="w-3 h-3 text-white" />
                                    )}
                                  </div>
                                </div>
                                <span className="text-sm text-gray-700 flex-1">{page}</span>
                              </label>
                            ))
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
               {/* Removed duplicate Select All Pages checkbox below dropdown */}
                <div className="h-4" />
                {/* Query Input */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Your Question
                  </label>
                  <textarea
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="What would you like to know about the selected content?"
                    className="w-full p-3 border border-white/30 rounded-lg focus:ring-2 focus:ring-confluence-blue focus:border-confluence-blue resize-none bg-white/70 backdrop-blur-sm"
                    rows={4}
                  />
                </div>

                {/* Search Button */}
                <button
                  onClick={handleSearch}
                  disabled={!selectedSpace || selectedPages.length === 0 || !query.trim() || isLoading}
                  className="w-full bg-confluence-blue/90 backdrop-blur-sm text-white py-3 px-4 rounded-lg hover:bg-confluence-blue disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center space-x-2 transition-colors border border-white/10"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Generating AI Response...</span>
                    </>
                  ) : (
                    <>
                      <Search className="w-5 h-5" />
                      <span>Generate AI Response</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Right Column - Results */}
            <div className="space-y-6">
              {response && (
                <div className="bg-white/60 backdrop-blur-xl rounded-xl p-4 border border-white/20 shadow-lg">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-gray-800">AI Response</h3>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => setShowRawContent(!showRawContent)}
                        className="text-sm text-confluence-blue hover:underline"
                      >
                        {showRawContent ? 'Show Formatted' : 'Show Raw Content'}
                      </button>
                    </div>
                  </div>
                  
                  <div className="bg-white/70 backdrop-blur-sm rounded-lg p-4 border border-white/20 max-h-80 overflow-y-auto">
                    {showRawContent ? (
                      <pre className="text-sm text-gray-700 whitespace-pre-wrap">{response}</pre>
                    ) : (
                      <div className="prose prose-sm max-w-none">
                        {response.split('\n').map((line, index) => {
                          if (line.startsWith('## ')) {
                            return <h2 key={index} className="text-lg font-bold text-gray-800 mt-4 mb-2">{line.substring(3)}</h2>;
                          } else if (line.startsWith('- **')) {
                            const match = line.match(/- \*\*(.*?)\*\*: (.*)/);
                            if (match) {
                              return <p key={index} className="mb-2"><strong>{match[1]}:</strong> {match[2]}</p>;
                            }
                          } else if (line.startsWith('- ')) {
                            return <p key={index} className="mb-1 ml-4">• {line.substring(2)}</p>;
                          } else if (line.trim()) {
                            return <p key={index} className="mb-2 text-gray-700">{line}</p>;
                          }
                          return <br key={index} />;
                        })}
                      </div>
                    )}
                  </div>

                  {/* Export Options */}
                  <div className="mt-4 space-y-3">
                    <div className="flex items-center space-x-2">
                      <label className="text-sm font-medium text-gray-700">Export Format:</label>
                      <select
                        value={exportFormat}
                        onChange={(e) => setExportFormat(e.target.value)}
                        className="px-3 py-1 border border-white/30 rounded text-sm focus:ring-2 focus:ring-confluence-blue bg-white/70 backdrop-blur-sm"
                      >
                        <option value="markdown">Markdown</option>
                        <option value="pdf">PDF</option>
                        <option value="docx">Word Document</option>
                        <option value="txt">Plain Text</option>
                      </select>
                    </div>
                    
                    <div className="flex space-x-2">
                      <button
                        onClick={() => exportResponse(exportFormat)}
                        className="flex items-center space-x-2 px-4 py-2 bg-green-600/90 backdrop-blur-sm text-white rounded-lg hover:bg-green-700 transition-colors border border-white/10"
                      >
                        <Download className="w-4 h-4" />
                        <span>Export</span>
                      </button>
                      <button
                        onClick={async () => {
                          const { space, page } = getConfluenceSpaceAndPageFromUrl();
                          if (!space || !page) {
                            alert('Confluence space or page not specified in macro src URL.');
                            return;
                          }
                          try {
                            await apiService.saveToConfluence({
                              space_key: space,
                              page_title: page,
                              content: response || '',
                            });
                            setShowToast(true);
                            setTimeout(() => setShowToast(false), 3000);
                          } catch (err: any) {
                            alert('Failed to save to Confluence: ' + (err.message || err));
                          }
                        }}
                        className="flex items-center space-x-2 px-4 py-2 bg-confluence-blue/90 backdrop-blur-sm text-white rounded-lg hover:bg-confluence-blue transition-colors border border-white/10"
                      >
                        <Save className="w-4 h-4" />
                        <span>Save to Confluence</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {!response && !isLoading && (
                <div className="bg-white/60 backdrop-blur-xl rounded-xl p-8 text-center border border-white/20 shadow-lg">
                  <FileText className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-gray-600 mb-2">Ready to Search</h3>
                  <p className="text-gray-500">Configure your search parameters and click "Generate AI Response" to get started.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      {showToast && (
        <div style={{position: 'fixed', bottom: 40, left: '50%', transform: 'translateX(-50%)', background: '#2684ff', color: 'white', padding: '16px 32px', borderRadius: 8, zIndex: 9999, fontWeight: 600, fontSize: 16, boxShadow: '0 2px 12px rgba(0,0,0,0.15)'}}>
          Saved to Confluence! Please refresh this Confluence page to see your changes.
        </div>
      )}
    </div>
  );
};

export default AIPoweredSearch;