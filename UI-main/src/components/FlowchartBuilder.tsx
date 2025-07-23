import React, { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

interface FlowchartBuilderProps {
  mermaidCode: string;
  detectedType: string;
  nodes: any[];
  edges: any[];
  rawContent: string;
  debug?: Record<string, any>;
}

const FlowchartBuilder: React.FC<FlowchartBuilderProps> = ({
  mermaidCode,
  detectedType,
  nodes,
  edges,
  rawContent,
  debug,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chartRef.current && mermaidCode) {
      mermaid.initialize({ startOnLoad: false, theme: 'default' });
      // Use the Promise-based API for mermaid.render
      (async () => {
        const { svg } = await mermaid.render('mermaid-flowchart', mermaidCode);
        if (chartRef.current) {
          chartRef.current.innerHTML = svg;
        }
      })();
    }
  }, [mermaidCode]);

  // Download as PNG
  const handleDownload = () => {
    if (!chartRef.current) return;
    const svg = chartRef.current.querySelector('svg');
    if (!svg) return;
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svg);
    const canvas = document.createElement('canvas');
    const img = new window.Image();
    const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);
    img.onload = function () {
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(img, 0, 0);
        const pngUrl = canvas.toDataURL('image/png');
        const a = document.createElement('a');
        a.href = pngUrl;
        a.download = 'flowchart.png';
        a.click();
        URL.revokeObjectURL(url);
      }
    };
    img.src = url;
  };

  return (
    <div className="bg-white/80 rounded-xl p-6 border border-white/20 shadow-lg mb-8">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-xl font-bold text-confluence-blue">Flowchart Builder</h3>
          <p className="text-gray-600 text-sm">Detected: <span className="font-semibold">{detectedType}</span></p>
        </div>
        <button
          onClick={handleDownload}
          className="bg-confluence-blue text-white px-4 py-2 rounded-lg hover:bg-confluence-blue/80 transition-colors"
        >
          Download as PNG
        </button>
      </div>
      <div ref={chartRef} className="w-full overflow-x-auto flex justify-center items-center min-h-[300px] bg-white/60 rounded-lg border border-white/10 p-4" />
      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <h4 className="font-semibold text-gray-800 mb-2">Nodes</h4>
          <pre className="bg-gray-100 rounded p-2 text-xs overflow-x-auto max-h-40">{JSON.stringify(nodes, null, 2)}</pre>
        </div>
        <div>
          <h4 className="font-semibold text-gray-800 mb-2">Edges</h4>
          <pre className="bg-gray-100 rounded p-2 text-xs overflow-x-auto max-h-40">{JSON.stringify(edges, null, 2)}</pre>
        </div>
      </div>
      <div className="mt-6">
        <h4 className="font-semibold text-gray-800 mb-2">Raw Content</h4>
        <pre className="bg-gray-50 rounded p-2 text-xs overflow-x-auto max-h-32">{rawContent}</pre>
      </div>
      {debug && (
        <div className="mt-6">
          <h4 className="font-semibold text-gray-800 mb-2">Debug Info</h4>
          <pre className="bg-yellow-50 rounded p-2 text-xs overflow-x-auto max-h-32">{JSON.stringify(debug, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default FlowchartBuilder; 