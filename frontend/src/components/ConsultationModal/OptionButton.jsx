import { CheckCircle2, Circle } from "lucide-react";

export default function OptionButton({
     option,
     isSelected,
     onClick,
     type,
     animationDelay
}) {
     const isMulti = type === 'multi_select';

     return (
          <button
               onClick={onClick}
               className={`
        w-full text-left
        border-2 rounded-xl
        px-6 py-4
        transition-all duration-300
        ${isSelected
                         ? 'border-accent bg-accent/10 shadow-neon'
                         : 'border-white/10 bg-glass hover:border-white/20 hover:bg-glass-hover'
                    }
        hover:-translate-y-0.5
        active:scale-[0.99]
        animate-in fade-in slide-in-from-bottom-2 duration-300
      `}
               style={{ animationDelay: `${animationDelay}ms` }}
          >
               <div className="flex items-center gap-4">
                    {/* Radio or Checkbox visual */}
                    <div className={`
          flex-shrink-0 w-6 h-6 flex items-center justify-center
          transition-colors
        `}>
                         {isSelected ? (
                              <CheckCircle2 className="w-6 h-6 text-accent fill-accent/20" />
                         ) : (
                              <Circle className="w-6 h-6 text-white/20" />
                         )}
                    </div>

                    {/* Label and Description */}
                    <div className="flex flex-col">
                         <span className={`
            font-semibold text-lg
            ${isSelected ? 'text-accent' : 'text-secondary'}
          `}>
                              {option.label}
                         </span>
                         {option.description && (
                              <span className="text-sm text-secondary/60">
                                   {option.description}
                              </span>
                         )}
                    </div>
               </div>
          </button>
     );
}
