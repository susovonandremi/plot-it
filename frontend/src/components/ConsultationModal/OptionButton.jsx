import { Check } from "lucide-react";

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
         border rounded-lg
         px-5 py-3.5
         transition-all duration-200
         ${isSelected
                        ? 'border-primary bg-primary/10 shadow-[0_0_12px_rgba(138,235,255,0.1)]'
                        : 'border-outline-variant/50 bg-glass hover:border-outline-variant hover:bg-glass-hover'
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
                        flex-shrink-0 w-4 h-4 flex items-center justify-center
                        border transition-colors
                        ${isMulti ? 'rounded-sm' : 'rounded-full'}
                        ${isSelected ? 'border-primary bg-primary/20 text-primary' : 'border-outline-variant text-transparent'}
                    `}>
                         {isSelected && <Check size={10} className="text-primary font-bold" />}
                    </div>

                    {/* Label and Description */}
                    <div className="flex flex-col">
                         <span className={`
                            font-semibold text-sm
                            ${isSelected ? 'text-primary' : 'text-on-surface'}
                         `}>
                              {option.label}
                         </span>
                         {option.description && (
                              <span className="text-xs text-on-surface-variant mt-0.5">
                                   {option.description}
                              </span>
                         )}
                    </div>
               </div>
          </button>
     );
}
