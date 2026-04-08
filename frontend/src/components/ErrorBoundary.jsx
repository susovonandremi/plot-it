import React from 'react';
import { AlertCircle } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
     constructor(props) {
          super(props);
          this.state = { hasError: false };
     }

     static getDerivedStateFromError(error) {
          // Update state so the next render will show the fallback UI.
          return { hasError: true };
     }

     componentDidCatch(error, errorInfo) {
          // You can also log the error to an error reporting service
          console.error("ErrorBoundary caught an error", error, errorInfo);
     }

     render() {
          if (this.state.hasError) {
               return (
                    <div className="flex flex-col items-center justify-center p-8 bg-neutral-900 border border-neutral-800 rounded-xl my-4 mx-auto max-w-sm text-center h-full">
                         <AlertCircle size={48} className="text-red-500 mb-4" />
                         <h2 className="text-lg font-bold text-white mb-2">Something went wrong</h2>
                         <p className="text-sm text-neutral-400 mb-4">An unexpected error occurred in this view. Try refreshing the page.</p>
                         <button 
                              onClick={() => window.location.reload()} 
                              className="px-4 py-2 bg-neutral-800 hover:bg-neutral-700 text-white rounded transition-colors text-sm font-medium"
                         >
                              Refresh App
                         </button>
                    </div>
               );
          }

          return this.props.children;
     }
}
