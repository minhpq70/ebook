'use client';
import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Loader2, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Maximize, Sparkles } from 'lucide-react';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export default function PDFViewer({ url, onTextSelect }: { url: string, onTextSelect?: (text: string) => void }) {
  const [numPages, setNumPages] = useState<number>();
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.0);
  const [loading, setLoading] = useState(true);
  const [selectionRect, setSelectionRect] = useState<{ top: number; left: number } | null>(null);
  const [selectedText, setSelectedText] = useState('');

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setLoading(false);
  }

  useEffect(() => {
    const handleMouseUp = () => {
      const selection = window.getSelection();
      const text = selection?.toString().trim();
      
      if (text && text.length > 0) {
        const range = selection?.getRangeAt(0);
        const rect = range?.getBoundingClientRect();
        
        // Cần lấy vị trí tương đối so với viewport
        if (rect) {
          // Điều chỉnh margin để nút hiển thị ngay trên dòng text
          setSelectionRect({
            top: rect.top - 40,
            left: rect.left + (rect.width / 2) - 60
          });
          setSelectedText(text);
        }
      } else {
        setSelectionRect(null);
        setSelectedText('');
      }
    };

    // Lắng nghe trên document vì PDF render có thể phức tạp
    document.addEventListener('mouseup', handleMouseUp);
    return () => document.removeEventListener('mouseup', handleMouseUp);
  }, []);

  const handleAskAI = () => {
    if (onTextSelect && selectedText) {
      onTextSelect(selectedText);
    }
    setSelectionRect(null);
    window.getSelection()?.removeAllRanges();
  };

  return (
    <div className="flex flex-col h-full bg-[#1e2130] rounded-xl overflow-hidden shadow-lg border border-[#2d3148]">
      {/* Toolbar */}
      <div className="flex items-center justify-between p-3 bg-[#0f1117] border-b border-[#2d3148]">
        <div className="flex items-center gap-2">
          <button 
            disabled={pageNumber <= 1}
            onClick={() => setPageNumber(p => p - 1)}
            className="p-1.5 hover:bg-[#2d3148] rounded text-[#8890a4] disabled:opacity-50"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className="text-sm text-white min-w-[80px] text-center font-mono">
            {pageNumber} / {numPages || '?'}
          </span>
          <button 
            disabled={pageNumber >= (numPages || 1)}
            onClick={() => setPageNumber(p => p + 1)}
            className="p-1.5 hover:bg-[#2d3148] rounded text-[#8890a4] disabled:opacity-50"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>

        <div className="flex items-center gap-2 border-l border-[#2d3148] pl-2 border-r pr-2">
          <button onClick={() => setScale(s => Math.max(0.5, s - 0.25))} className="p-1.5 hover:bg-[#2d3148] rounded text-[#8890a4]">
            <ZoomOut className="w-4 h-4" />
          </button>
          <span className="text-xs text-[#8890a4] w-12 text-center font-mono">{Math.round(scale * 100)}%</span>
          <button onClick={() => setScale(s => Math.min(3, s + 0.25))} className="p-1.5 hover:bg-[#2d3148] rounded text-[#8890a4]">
            <ZoomIn className="w-4 h-4" />
          </button>
          <button onClick={() => setScale(1)} className="p-1.5 hover:bg-[#2d3148] rounded text-[#8890a4] ml-1">
            <Maximize className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Viewer Area */}
      <div className="flex-1 overflow-auto relative pdf-container bg-[#1e2130] flex justify-center py-6">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#1e2130]/80 z-10">
            <Loader2 className="w-8 h-8 text-[#6c63ff] animate-spin" />
          </div>
        )}
        <Document
          file={url}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={null}
          className="pdf-document drop-shadow-xl"
        >
           <Page 
             pageNumber={pageNumber} 
             scale={scale} 
             renderTextLayer={true}
             renderAnnotationLayer={true}
             className="bg-white"
           />
        </Document>

        {/* Text Selection Popup */}
        {selectionRect && (
          <button
            onClick={handleAskAI}
            style={{
              position: 'fixed',
              top: selectionRect.top,
              left: selectionRect.left,
              zIndex: 100,
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#6c63ff] hover:bg-[#5b54ff] text-white text-sm font-medium rounded-full shadow-lg shadow-[#6c63ff]/20 animate-fade-in"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Hỏi AI</span>
          </button>
        )}
      </div>

      <style jsx global>{`
        .pdf-container {
          /* Custom scrollbar cho PDF area */
          scrollbar-width: thin;
          scrollbar-color: #2d3148 transparent;
        }
        .pdf-container::-webkit-scrollbar { width: 8px; height: 8px; }
        .pdf-container::-webkit-scrollbar-track { background: transparent; }
        .pdf-container::-webkit-scrollbar-thumb { background-color: #2d3148; border-radius: 4px; }
        
        /* Chỉnh CSS của react-pdf để tương phản tốt trên nền tối */
        .react-pdf__Page {
           border-radius: 4px;
           overflow: hidden;
           margin: 0 auto;
        }
        .react-pdf__Page__textContent {
           /* Hỗ trợ select text cho tool Hỏi AI */
           ::selection {
             background: rgba(108, 99, 255, 0.3) !important;
             color: currentColor;
           }
        }
      `}</style>
    </div>
  );
}
