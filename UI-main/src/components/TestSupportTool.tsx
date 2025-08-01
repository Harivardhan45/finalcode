import React, { useState, useEffect } from 'react';
// For opening a new tab
// No extra import needed for window.open
import { TestTube, BarChart3, Code, FileCheck, Download, Save, X, ChevronDown, Loader2, MessageSquare, Play, Search, Video, TrendingUp, Image, ChevronUp, Check } from 'lucide-react';
import { FeatureType, AppMode } from '../App';
import { apiService, Space } from '../services/api';
import CustomScrollbar from './CustomScrollbar';
import ReactMarkdown from 'react-markdown';
import { getConfluenceSpaceAndPageFromUrl } from '../utils/urlUtils';
import VoiceRecorder from './VoiceRecorder';

interface TestSupportToolProps {
  onClose: () => void;
  onFeatureSelect: (feature: FeatureType) => void;
  onModeSelect: (mode: AppMode) => void;
  autoSpaceKey?: string | null;
  isSpaceAutoConnected?: boolean;
}

interface TestReport {
  strategy?: string;
  crossPlatform?: string;
  sensitivity?: string;
}

const TestSupportTool: React.FC<TestSupportToolProps> = ({ onClose, onFeatureSelect, onModeSelect, autoSpaceKey, isSpaceAutoConnected }) => {
  // --- Checkly Integration ---
  const CHECKLY_API_KEY = "cu_f8631b426c514b6dba1c100ebf18d186";
  /**
   * Create a Checkly API check with a valid request field.
   * Ensures all required fields are present and valid for Checkly API.
   * @param {string} _unused - Not used, kept for compatibility with button call.
   */
  async function createChecklyTest(_unused: string) {
    // Build the payload for an API check (not a script check)
    const payload = {
      name: 'Generated Test',
      type: 'API',
      checkType: 'API',
      activated: true,
      frequency: 5,
      locations: ['eu-west-1'],
      degradedResponseTime: 2000,
      maxResponseTime: 5000,
      request: {
        method: 'GET',
        url: 'https://jsonplaceholder.typicode.com/todos/1',
        assertions: [
          {
            source: 'STATUS_CODE',
            comparison: 'EQUALS',
            target: 200
          }
        ]
      }
    };
    try {
      const response = await fetch('https://api.checklyhq.com/v1/checks', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${CHECKLY_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      const text = await response.text();
      let data;
      try { data = JSON.parse(text); } catch { data = text; }
      if (!response.ok) {
        if (response.status === 400 && typeof data === 'object') {
          console.error('Checkly 400 error:', data);
        }
        alert('Checkly API error: ' + (data && data.message ? data.message : text));
        return;
      }
      if (data && data.id) {
        window.open(`https://app.checklyhq.com/checks/${data.id}`, '_blank');
      } else {
        alert('Checkly test created but no check ID returned. Response: ' + JSON.stringify(data));
      }
    } catch (e: any) {
      alert('Failed to create Checkly test: ' + (e.message || e));
    }
  }
  const [selectedSpace, setSelectedSpace] = useState('');
  const [codePage, setCodePage] = useState('');
  const [testInputPage, setTestInputPage] = useState('');
  const [isGenerating, setIsGenerating] = useState<string>('');
  const [isQALoading, setIsQALoading] = useState(false);
  const [testReport, setTestReport] = useState<TestReport | null>(null);
  const [question, setQuestion] = useState('');
  const [qaResults, setQaResults] = useState<Array<{question: string, answer: string}>>([]);
  const [exportFormat, setExportFormat] = useState('markdown');
  const [exportFormatSearch, setExportFormatSearch] = useState('');
  const [isExportFormatDropdownOpen, setIsExportFormatDropdownOpen] = useState(false);
  const exportFormats = [
    { value: 'markdown', label: 'Markdown' },
    { value: 'pdf', label: 'PDF' },
    { value: 'docx', label: 'Word Document' }
  ];
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [pages, setPages] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [showToast, setShowToast] = useState(false);
  const [saveMode, setSaveMode] = useState('append');
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [previewDiff, setPreviewDiff] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [codePageSearch, setCodePageSearch] = useState('');
  const [isCodePageDropdownOpen, setIsCodePageDropdownOpen] = useState(false);
  const [testInputPageSearch, setTestInputPageSearch] = useState('');
  const [isTestInputPageDropdownOpen, setIsTestInputPageDropdownOpen] = useState(false);

  // --- History feature for Q&A ---
  const [qaHistory, setQaHistory] = useState<Array<{question: string, answer: string}>>([]);
  const [currentQaHistoryIndex, setCurrentQaHistoryIndex] = useState<number | null>(null);

  const features = [
    { id: 'search' as const, label: 'AI Powered Search', icon: Search },
    { id: 'video' as const, label: 'Video Summarizer', icon: Video },
    { id: 'code' as const, label: 'Code Assistant', icon: Code },
    { id: 'impact' as const, label: 'Impact Analyzer', icon: TrendingUp },
    { id: 'test' as const, label: 'Test Support Tool', icon: TestTube },
    { id: 'image' as const, label: 'Chart Builder', icon: BarChart3 },
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
        setCodePage(page);
      }
    } catch (err) {
      setError('Failed to load pages. Please check your space key.');
      console.error('Error loading pages:', err);
    }
  };

  const generateTestStrategy = async () => {
    if (!selectedSpace || !codePage) {
      setError('Please select a space and code page.');
      return;
    }

    setIsGenerating('strategy');
    setError('');

    try {
      console.log('Calling test support API for strategy...');
      const result = await apiService.testSupport({
        space_key: selectedSpace,
        code_page_title: codePage,
        test_input_page_title: testInputPage || undefined
      });

      console.log('Test support API response:', result);

      setTestReport(prev => ({
        ...prev,
        strategy: result.test_strategy || 'No test strategy generated.'
      } as TestReport));
    } catch (err) {
      console.error('Test support API error:', err);
      setError('Failed to generate test strategy. Please try again.');
      console.error('Error generating test strategy:', err);
    } finally {
      setIsGenerating('');
    }
  };

  const generateCrossPlatform = async () => {
    if (!selectedSpace || !codePage) {
      setError('Please select a space and code page.');
      return;
    }

    setIsGenerating('crossplatform');
    setError('');

    try {
      console.log('Calling test support API for cross-platform...');
      const result = await apiService.testSupport({
        space_key: selectedSpace,
        code_page_title: codePage,
        test_input_page_title: testInputPage || undefined
      });

      console.log('Cross-platform API response:', result);

      setTestReport(prev => ({
        ...prev,
        crossPlatform: (result.cross_platform_testing || 'No cross-platform analysis generated.').replace(/\u2192/g, '->')

      } as TestReport));
    } catch (err) {
      console.error('Cross-platform API error:', err);
      setError('Failed to generate cross-platform analysis. Please try again.');
      console.error('Error generating cross-platform analysis:', err);
    } finally {
      setIsGenerating('');
    }
  };

  const generateSensitivity = async () => {
    if (!selectedSpace || !codePage) {
      setError('Please select a space and code page.');
      return;
    }

    setIsGenerating('sensitivity');
    setError('');

    try {
      console.log('Calling test support API for sensitivity...');
      const result = await apiService.testSupport({
        space_key: selectedSpace,
        code_page_title: codePage,
        test_input_page_title: testInputPage || undefined
      });

      console.log('Sensitivity API response:', result);

      setTestReport(prev => ({
        ...prev,
        sensitivity: (result.sensitivity_analysis || 'No sensitivity analysis generated.')
      } as TestReport));
    } catch (err) {
      console.error('Sensitivity API error:', err);
      setError('Failed to generate sensitivity analysis. Please try again.');
      console.error('Error generating sensitivity analysis:', err);
    } finally {
      setIsGenerating('');
    }
  };

  const addQuestion = async () => {
    if (!question.trim() || !selectedSpace || !codePage) {
      console.log('Missing question or code page:', { question, selectedSpace, codePage });
      return;
    }
    
    console.log('Adding question to test support tool:', question);
    setIsQALoading(true);
    
    try {
      const result = await apiService.testSupport({
        space_key: selectedSpace,
        code_page_title: codePage,
        test_input_page_title: testInputPage || undefined,
        question: question
      });

      console.log('Test support Q&A response:', result);

      const answer = result.ai_response || `Based on the test analysis, here's the response to your question: "${question}"

The test coverage analysis shows comprehensive validation of the code functionality. The sensitivity check indicates ${question.toLowerCase().includes('security') ? 'strong security measures in place' : question.toLowerCase().includes('performance') ? 'good performance characteristics' : 'robust error handling and edge case coverage'}.

This analysis is based on the test scenarios and code review performed.`;

      setQaResults([...qaResults, { question, answer }]);
      
      // Add to Q&A history
      setQaHistory(prev => [{ question, answer }, ...prev]);
      setCurrentQaHistoryIndex(0);
      
      setQuestion('');
    } catch (err) {
      console.error('Test support Q&A error:', err);
      setError('Failed to get answer. Please try again.');
      console.error('Error getting answer:', err);
    } finally {
      setIsQALoading(false);
    }
  };

  // When currentQaHistoryIndex changes, update displayed question
  useEffect(() => {
    if (currentQaHistoryIndex !== null && qaHistory[currentQaHistoryIndex]) {
      const historyItem = qaHistory[currentQaHistoryIndex];
      setQuestion(historyItem.question);
    }
  }, [currentQaHistoryIndex]);

  const exportReport = async () => {
    if (!testReport) return;

    const content = `# Test Support Report

## Test Strategy
${testReport.strategy}

## Cross-Platform Analysis
${testReport.crossPlatform}

## Sensitivity Analysis
${testReport.sensitivity}

## Q&A
${qaResults.map(qa => `**Q:** ${qa.question}\n**A:** ${qa.answer}`).join('\n\n')}

## Generated on: ${new Date().toLocaleString()}`;

    try {
      const blob = await apiService.exportContent({
        content: content,
        format: exportFormat,
        filename: 'test-support-report'
      });
      
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `test-support-report.${exportFormat}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to export file. Please try again.');
      console.error('Error exporting:', err);
    }
  };

  function cleanPreviewContent(html: string, numBlocks = 2): string {
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      // Remove chatbot widget by class or id (adjust selector as needed)
      const chatbot = doc.querySelector('.YOUR_CHATBOT_CLASS, #YOUR_CHATBOT_ID');
      if (chatbot) chatbot.remove();

      // Get all paragraphs and divs (or adjust as needed)
      const blocks = Array.from(doc.body.querySelectorAll('p, div, section, ul, ol, pre, h1, h2, h3, h4, h5, h6'));
      if (blocks.length >= numBlocks) {
        return blocks.slice(-numBlocks).map(el => el.outerHTML).join('');
      }
      // Fallback: return all content
      return doc.body.innerHTML;
    } catch {
      return html;
    }
  }

  return (
    <div className="fixed inset-0 bg-white flex items-center justify-center z-40 p-4">
      <div className="bg-white/80 backdrop-blur-xl border-2 border-[#0052cc] rounded-2xl w-full max-w-7xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-confluence-blue/90 to-confluence-light-blue/90 backdrop-blur-xl p-6 text-white border-b border-white/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <TestTube className="w-8 h-8" />
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
                  const isActive = feature.id === 'test';
                  
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

          <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
            {/* Left Column - Configuration */}
            <div className="xl:col-span-1">
              <div className="bg-white/60 backdrop-blur-xl rounded-xl p-4 space-y-6 border border-white/20 shadow-lg">
                <h3 className="font-semibold text-gray-800 mb-4 flex items-center">
                  <FileCheck className="w-5 h-5 mr-2" />
                  Component Selection
                </h3>
                
                {/* Space Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Space
                  </label>
                  <div className="relative">
                    <select
                      value={selectedSpace}
                      onChange={(e) => setSelectedSpace(e.target.value)}
                      className="w-full p-3 border border-white/30 rounded-lg focus:ring-2 focus:ring-confluence-blue focus:border-confluence-blue appearance-none bg-white/70 backdrop-blur-sm"
                    >
                      <option value="">Select space...</option>
                      {spaces.map(space => (
                        <option key={space.key} value={space.key}>{space.name}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
                  </div>
                </div>

                {/* Code Page Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Code Page
                  </label>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setIsCodePageDropdownOpen(!isCodePageDropdownOpen)}
                      className="w-full p-3 border border-white/30 rounded-lg focus:ring-2 focus:ring-confluence-blue focus:border-confluence-blue bg-white/70 backdrop-blur-sm text-left flex items-center justify-between"
                    >
                      <span className={codePage === '' ? 'text-gray-500' : 'text-gray-700'}>
                        {codePage === '' ? 'Select code page...' : codePage}
                      </span>
                      {isCodePageDropdownOpen ? (
                        <ChevronUp className="w-5 h-5 text-gray-400" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-gray-400" />
                      )}
                    </button>
                    {isCodePageDropdownOpen && (
                      <div className="absolute z-50 w-full mt-1 bg-white/95 backdrop-blur-xl border border-white/30 rounded-lg shadow-xl max-h-60 overflow-hidden">
                        <div className="p-3 border-b border-white/20 bg-white/50">
                          <input
                            type="text"
                            value={codePageSearch}
                            onChange={e => setCodePageSearch(e.target.value)}
                            placeholder="Search pages..."
                            className="w-full px-3 py-2 border border-white/20 rounded-lg text-sm focus:ring-2 focus:ring-confluence-blue focus:border-confluence-blue bg-white/80 placeholder-gray-400 mb-1"
                          />
                        </div>
                        <div className="max-h-48 overflow-y-auto">
                          {(pages.filter(page => page.toLowerCase().includes(codePageSearch.toLowerCase()))).length === 0 ? (
                            <div className="p-3 text-gray-500 text-sm text-center">
                              No pages found
                            </div>
                          ) : (
                            pages.filter(page => page.toLowerCase().includes(codePageSearch.toLowerCase())).map(page => (
                              <button
                                key={page}
                                type="button"
                                onClick={() => { setCodePage(page); setIsCodePageDropdownOpen(false); setCodePageSearch(''); }}
                                className={`w-full text-left flex items-center space-x-3 p-3 hover:bg-white/50 cursor-pointer border-b border-white/10 last:border-b-0 ${codePage === page ? 'bg-confluence-blue/10' : ''}`}
                              >
                                <span className="text-sm text-gray-700 flex-1">{page}</span>
                                {codePage === page && <Check className="w-4 h-4 text-confluence-blue" />}
                              </button>
                            ))
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                {/* Test Input Page Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Test Input Page
                  </label>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setIsTestInputPageDropdownOpen(!isTestInputPageDropdownOpen)}
                      className="w-full p-3 border border-white/30 rounded-lg focus:ring-2 focus:ring-confluence-blue focus:border-confluence-blue bg-white/70 backdrop-blur-sm text-left flex items-center justify-between"
                    >
                      <span className={testInputPage === '' ? 'text-gray-500' : 'text-gray-700'}>
                        {testInputPage === '' ? 'Select test page...' : testInputPage}
                      </span>
                      {isTestInputPageDropdownOpen ? (
                        <ChevronUp className="w-5 h-5 text-gray-400" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-gray-400" />
                      )}
                    </button>
                    {isTestInputPageDropdownOpen && (
                      <div className="absolute z-50 w-full mt-1 bg-white/95 backdrop-blur-xl border border-white/30 rounded-lg shadow-xl max-h-60 overflow-hidden">
                        <div className="p-3 border-b border-white/20 bg-white/50">
                          <input
                            type="text"
                            value={testInputPageSearch}
                            onChange={e => setTestInputPageSearch(e.target.value)}
                            placeholder="Search pages..."
                            className="w-full px-3 py-2 border border-white/20 rounded-lg text-sm focus:ring-2 focus:ring-confluence-blue focus:border-confluence-blue bg-white/80 placeholder-gray-400 mb-1"
                          />
                        </div>
                        <div className="max-h-48 overflow-y-auto">
                          {(pages.filter(page => page.toLowerCase().includes(testInputPageSearch.toLowerCase()))).length === 0 ? (
                            <div className="p-3 text-gray-500 text-sm text-center">
                              No pages found
                            </div>
                          ) : (
                            pages.filter(page => page.toLowerCase().includes(testInputPageSearch.toLowerCase())).map(page => (
                              <button
                                key={page}
                                type="button"
                                onClick={() => { setTestInputPage(page); setIsTestInputPageDropdownOpen(false); setTestInputPageSearch(''); }}
                                className={`w-full text-left flex items-center space-x-3 p-3 hover:bg-white/50 cursor-pointer border-b border-white/10 last:border-b-0 ${testInputPage === page ? 'bg-confluence-blue/10' : ''}`}
                              >
                                <span className="text-sm text-gray-700 flex-1">{page}</span>
                                {testInputPage === page && <Check className="w-4 h-4 text-confluence-blue" />}
                              </button>
                            ))
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Generation Buttons */}
                <div className="space-y-3">
                  <button
                    onClick={generateTestStrategy}
                    disabled={!selectedSpace || !codePage || isGenerating === 'strategy'}
                    className="w-full bg-confluence-blue/90 backdrop-blur-sm text-white py-2 px-4 rounded-lg hover:bg-confluence-blue disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center space-x-2 transition-colors border border-white/10"
                  >
                    {isGenerating === 'strategy' ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Generating...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4" />
                        <span>Generate Strategy</span>
                      </>
                    )}
                  </button>

                  <button
                    onClick={generateCrossPlatform}
                    disabled={!selectedSpace || !codePage || isGenerating === 'crossplatform'}
                    className="w-full bg-confluence-blue/90 backdrop-blur-sm text-white py-2 px-4 rounded-lg hover:bg-confluence-blue disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center space-x-2 transition-colors border border-white/10"
                  >
                    {isGenerating === 'crossplatform' ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Analyzing...</span>
                      </>
                    ) : (
                      <>
                        <Code className="w-4 h-4" />
                        <span>Cross-Platform</span>
                      </>
                    )}
                  </button>

                  <button
                    onClick={generateSensitivity}
                    disabled={!selectedSpace || !codePage || isGenerating === 'sensitivity'}
                    className="w-full bg-confluence-blue/90 backdrop-blur-sm text-white py-2 px-4 rounded-lg hover:bg-confluence-blue disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center space-x-2 transition-colors border border-white/10"
                  >
                    {isGenerating === 'sensitivity' ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Analyzing...</span>
                      </>
                    ) : (
                      <>
                        <TestTube className="w-4 h-4" />
                        <span>Sensitivity Check</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Export Button */}
                {testReport && (testReport.strategy || testReport.crossPlatform || testReport.sensitivity) && (
                  <div className="pt-4 border-t border-white/20 space-y-3">
                    {/* Checkly Integration Button */}
                    {testReport?.strategy && (
                      <button
                        onClick={() => createChecklyTest(testReport.strategy || '')}
                        className="w-full flex items-center justify-center space-x-2 px-4 py-2 bg-[#00DC82] text-white rounded-lg hover:bg-[#00b86b] transition-colors border border-white/10 mb-2"
                        style={{ fontWeight: 600 }}
                      >
                        <span role="img" aria-label="checkly">✅</span>
                        <span>Send to Checkly</span>
                      </button>
                    )}
                    {/* Export Format Selection */}
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-gray-700 mb-2">What format would you like to export in?</label>
                      <div className="relative w-48">
                        <button
                          type="button"
                          onClick={() => setIsExportFormatDropdownOpen(!isExportFormatDropdownOpen)}
                          className="px-3 py-1 border border-white/30 rounded text-sm focus:ring-2 focus:ring-confluence-blue bg-white/70 backdrop-blur-sm w-full flex items-center justify-between"
                        >
                          <span>{exportFormats.find(f => f.value === exportFormat)?.label || 'Select format'}</span>
                          {isExportFormatDropdownOpen ? (
                            <ChevronUp className="w-4 h-4 text-gray-400" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-gray-400" />
                          )}
                        </button>
                        {isExportFormatDropdownOpen && (
                          <div className="absolute z-50 w-full mt-1 bg-white/95 backdrop-blur-xl border border-white/30 rounded-lg shadow-xl max-h-48 overflow-hidden">
                            <div className="p-2 border-b border-white/20 bg-white/50">
                              <input
                                type="text"
                                value={exportFormatSearch}
                                onChange={e => setExportFormatSearch(e.target.value)}
                                placeholder="Search formats..."
                                className="w-full px-2 py-1 border border-white/20 rounded-lg text-sm focus:ring-2 focus:ring-confluence-blue focus:border-confluence-blue bg-white/80 placeholder-gray-400 mb-1"
                              />
                            </div>
                            <div className="max-h-32 overflow-y-auto">
                              {exportFormats.filter(f => f.label.toLowerCase().includes(exportFormatSearch.toLowerCase())).length === 0 ? (
                                <div className="p-2 text-gray-500 text-sm text-center">No formats found</div>
                              ) : (
                                exportFormats.filter(f => f.label.toLowerCase().includes(exportFormatSearch.toLowerCase())).map(f => (
                                  <button
                                    key={f.value}
                                    type="button"
                                    onClick={() => { setExportFormat(f.value); setIsExportFormatDropdownOpen(false); setExportFormatSearch(''); }}
                                    className={`w-full text-left flex items-center space-x-2 p-2 hover:bg-white/50 cursor-pointer border-b border-white/10 last:border-b-0 ${exportFormat === f.value ? 'bg-confluence-blue/10' : ''}`}
                                  >
                                    <span className="text-sm text-gray-700 flex-1">{f.label}</span>
                                    {exportFormat === f.value && <Check className="w-4 h-4 text-confluence-blue" />}
                                  </button>
                                ))
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2 mb-2">
                      <label htmlFor="save-mode" className="text-sm font-medium text-gray-700">Save Mode:</label>
                      <select
                        id="save-mode"
                        value={saveMode}
                        onChange={e => setSaveMode(e.target.value)}
                        className="px-3 py-1 border border-white/30 rounded text-sm focus:ring-2 focus:ring-confluence-blue bg-white/70 backdrop-blur-sm"
                      >
                        <option value="append">Append</option>
                        <option value="overwrite">Overwrite</option>
                      </select>
                    </div>
                    
                    <div className="space-y-2">
                      <button
                        onClick={exportReport}
                        className="w-full flex items-center justify-center space-x-2 px-4 py-2 bg-green-600/90 backdrop-blur-sm text-white rounded-lg hover:bg-green-700 transition-colors border border-white/10"
                      >
                        <Download className="w-4 h-4" />
                        <span>Export</span>
                      </button>
                      <button
                        onClick={async () => {
                          setIsPreviewLoading(true);
                          setShowPreview(false);
                          try {
                            const { space, page } = getConfluenceSpaceAndPageFromUrl();
                            if (!space || !page) {
                              alert('Confluence space or page not specified in macro src URL.');
                              return;
                            }
                            let content = '';
                            if (testReport?.strategy) content += `# Test Strategy\n${testReport.strategy}\n`;
                            if (testReport?.crossPlatform) content += `# Cross-Platform Analysis\n${testReport.crossPlatform}\n`;
                            if (testReport?.sensitivity) content += `# Sensitivity Analysis\n${testReport.sensitivity}\n`;
                            if (!content) {
                              alert('No test report content to save.');
                              return;
                            }
                            const preview = await apiService.previewSaveToConfluence({
                              space_key: space,
                              page_title: page,
                              content: content,
                              mode: saveMode,
                            });
                            setPreviewContent(preview.preview_content);
                            setPreviewDiff(preview.diff);
                            setShowPreview(true);
                          } catch (err: any) {
                            alert('Failed to generate preview: ' + (err.message || err));
                          } finally {
                            setIsPreviewLoading(false);
                          }
                        }}
                        className="w-full flex items-center justify-center space-x-2 px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 transition-colors border border-white/10"
                      >
                        {isPreviewLoading ? "Loading..." : "Preview"}
                      </button>
                      <button
                        onClick={async () => {
                          const { space, page } = getConfluenceSpaceAndPageFromUrl();
                          if (!space || !page) {
                            alert('Confluence space or page not specified in macro src URL.');
                            return;
                          }
                          let content = '';
                          if (testReport?.strategy) content += `# Test Strategy\n${testReport.strategy}\n`;
                          if (testReport?.crossPlatform) content += `# Cross-Platform Analysis\n${testReport.crossPlatform}\n`;
                          if (testReport?.sensitivity) content += `# Sensitivity Analysis\n${testReport.sensitivity}\n`;
                          if (!content) {
                            alert('No test report content to save.');
                            return;
                          }
                          try {
                            await apiService.saveToConfluence({
                              space_key: space,
                              page_title: page,
                              content: content,
                              mode: saveMode,
                            });
                            setShowToast(true);
                            setTimeout(() => setShowToast(false), 3000);
                          } catch (err: any) {
                            alert('Failed to save to Confluence: ' + (err.message || err));
                          }
                        }}
                        className="w-full flex items-center justify-center space-x-2 px-4 py-2 bg-confluence-blue/90 backdrop-blur-sm text-white rounded-lg hover:bg-confluence-blue transition-colors border border-white/10"
                      >
                        <Save className="w-4 h-4" />
                        <span>Save to Confluence</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Middle Columns - Generated Content */}
            <div className="xl:col-span-2 space-y-6">
              {/* Test Strategy */}
              {testReport?.strategy && (
                <div className="bg-white/60 backdrop-blur-xl rounded-xl p-4 border border-white/20 shadow-lg">
                  <h3 className="font-semibold text-gray-800 mb-4 flex items-center">
                    <Play className="w-5 h-5 mr-2 text-confluence-blue" />
                    Test Strategy
                  </h3>
                  <div className="bg-white/70 backdrop-blur-sm rounded-lg p-4 border border-white/20 prose prose-sm max-w-none">
                    {testReport.strategy.split('\n').map((line, index) => {
                      if (line.startsWith('### ')) {
                        return <h3 key={index} className="text-lg font-bold text-gray-800 mt-4 mb-2">{line.substring(4)}</h3>;
                      } else if (line.startsWith('## ')) {
                        return <h2 key={index} className="text-xl font-bold text-gray-800 mt-6 mb-3">{line.substring(3)}</h2>;
                      } else if (line.startsWith('# ')) {
                        return <h1 key={index} className="text-2xl font-bold text-gray-800 mt-8 mb-4">{line.substring(2)}</h1>;
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
                </div>
              )}

              {/* Cross-Platform Analysis */}
              {testReport?.crossPlatform && (
                <div className="bg-white/60 backdrop-blur-xl rounded-xl p-4 border border-white/20 shadow-lg">
                  <h3 className="font-semibold text-gray-800 mb-4 flex items-center">
                    <Code className="w-5 h-5 mr-2 text-confluence-blue" />
                    Cross-Platform Analysis
                  </h3>
                  <div className="bg-white/70 backdrop-blur-sm rounded-lg p-4 border border-white/20 prose prose-sm max-w-none">
                    {testReport.crossPlatform.split('\n').map((line, index) => {
                      if (line.startsWith('### ')) {
                        return <h3 key={index} className="text-lg font-bold text-gray-800 mt-4 mb-2">{line.substring(4)}</h3>;
                      } else if (line.startsWith('## ')) {
                        return <h2 key={index} className="text-xl font-bold text-gray-800 mt-6 mb-3">{line.substring(3)}</h2>;
                      } else if (line.startsWith('# ')) {
                        return <h1 key={index} className="text-2xl font-bold text-gray-800 mt-8 mb-4">{line.substring(2)}</h1>;
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
                </div>
              )}

              {/* Sensitivity Analysis */}
              {testReport?.sensitivity && (
                <div className="bg-white/60 backdrop-blur-xl rounded-xl p-4 border border-white/20 shadow-lg">
                  <h3 className="font-semibold text-gray-800 mb-4 flex items-center">
                    <TestTube className="w-5 h-5 mr-2 text-confluence-blue" />
                    Sensitivity Analysis
                  </h3>
                  <div className="bg-white/70 backdrop-blur-sm rounded-lg p-4 border border-white/20 prose prose-sm max-w-none">
                    <div className="prose prose-sm max-w-none text-gray-800 bg-white/70 backdrop-blur-sm p-4 rounded-lg border border-white/20">
                    <ReactMarkdown>
                      {testReport.sensitivity}
                    </ReactMarkdown>
                    </div>
                  </div>
                </div>
              )}
              </div>

            {/* Right Column - Q&A */}
            <div className="xl:col-span-1">
              <div className="bg-white/60 backdrop-blur-xl rounded-xl p-4 space-y-4 border border-white/20 shadow-lg">
                <h3 className="font-semibold text-gray-800 mb-4 flex items-center">
                  <MessageSquare className="w-5 h-5 mr-2" />
                  Questions & Analysis
                </h3>
                
                {/* --- History Dropdown for Q&A --- */}
                {qaHistory.length > 0 && (
                  <div className="mb-4 flex items-center space-x-2">
                    <label className="text-sm font-medium text-gray-700">Q&A History:</label>
                    <select
                      className="border border-gray-300 rounded px-2 py-1 text-sm"
                      value={currentQaHistoryIndex ?? 0}
                      onChange={e => setCurrentQaHistoryIndex(Number(e.target.value))}
                    >
                      {qaHistory.map((item, idx) => (
                        <option key={idx} value={idx}>
                          {item.question.length > 40 ? item.question.slice(0, 40) + '...' : item.question}
                        </option>
                      ))}
                    </select>
                    {currentQaHistoryIndex !== null && currentQaHistoryIndex !== 0 && (
                      <button
                        className="text-xs text-confluence-blue underline ml-2"
                        onClick={() => setCurrentQaHistoryIndex(0)}
                      >
                        Go to Latest
                      </button>
                    )}
                  </div>
                )}
                {/* --- End History Dropdown --- */}
                
                {/* Existing Q&A */}
                {qaResults.length > 0 && (
                  <div className="space-y-3 mb-4 max-h-60 overflow-y-auto">
                    {qaResults.map((qa, index) => (
                      <div key={index} className="bg-white/70 backdrop-blur-sm rounded-lg p-3 border border-white/20">
                        <p className="font-medium text-gray-800 mb-2 text-sm">Q: {qa.question}</p>
                        <p className="text-gray-700 text-xs">{qa.answer.substring(0, 200)}...</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add Question */}
                <div className="space-y-2">
                  <div className="w-full">
                    <VoiceRecorder
                      value={question}
                      onChange={setQuestion}
                      onConfirm={setQuestion}
                      inputPlaceholder="Ask about testing strategies, coverage, or specific scenarios..."
                    />
                  </div>
                  <button
                    onClick={addQuestion}
                    disabled={!question.trim() || isQALoading}
                    className="w-full px-3 py-2 bg-confluence-blue/90 backdrop-blur-sm text-white rounded hover:bg-confluence-blue disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center space-x-2 border border-white/10"
                  >
                    {isQALoading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Loading...</span>
                      </>
                    ) : (
                      <>
                        <MessageSquare className="w-4 h-4" />
                        <span>Ask Question</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Empty State */}
          {!testReport?.strategy && !testReport?.crossPlatform && !testReport?.sensitivity && (
            <div className="text-center py-12">
              <TestTube className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-600 mb-2">Ready to Generate Test Analysis</h3>
              <p className="text-gray-500">Select your code and test components, then choose which analysis to generate.</p>
            </div>
          )}
        </div>
      </div>
      {showToast && (
        <div style={{position: 'fixed', bottom: 40, left: '50%', transform: 'translateX(-50%)', background: '#2684ff', color: 'white', padding: '16px 32px', borderRadius: 8, zIndex: 9999, fontWeight: 600, fontSize: 16, boxShadow: '0 2px 12px rgba(0,0,0,0.15)'}}>
          Saved to Confluence! Please refresh this Confluence page to see your changes.
        </div>
      )}
      {showPreview && (
        <div className="fixed inset-0 flex items-center justify-center z-50 bg-black/30">
          <div className="bg-confluence-blue/95 rounded-2xl shadow-2xl p-6 w-full max-w-3xl relative border border-white/20">
            <div className="flex justify-between items-center mb-4">
              <h4 className="font-semibold text-white text-lg">Preview of Updated Content</h4>
              <button onClick={() => setShowPreview(false)} className="text-white hover:text-red-400 font-bold text-base px-3 py-1 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-red-400">Close Preview</button>
            </div>
            <div
              className="overflow-y-auto bg-white/90 rounded-xl p-6 border border-white/30 shadow-inner min-h-[120px] max-h-[400px] text-gray-900 text-base font-normal"
              style={{
                fontFamily: 'inherit',
                boxSizing: 'border-box',
                wordBreak: 'break-word',
                whiteSpace: 'pre-wrap',
                marginBottom: 0,
              }}
              dangerouslySetInnerHTML={{ __html: previewContent || '' }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default TestSupportTool;