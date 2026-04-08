import { Progress } from "@/components/ui/progress";

export default function ProgressBar({ current, total }) {
     const progress = total > 0 ? (current / total) * 100 : 0;

     return (
          <div className="w-full space-y-2 mb-8">
               <div className="flex justify-between items-center text-xs font-mono text-secondary/60 uppercase tracking-wider">
                    <span>Progress</span>
                    <span className="text-accent">{Math.round(progress)}%</span>
               </div>
               <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-accent shadow-neon transition-all duration-300" style={{ width: `${progress}%` }} />
               </div>
          </div>
     );
}
