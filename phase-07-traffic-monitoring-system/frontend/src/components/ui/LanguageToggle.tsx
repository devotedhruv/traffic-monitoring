import { Languages } from "lucide-react";
import { useLanguage } from "../../app/LanguageContext";

export function LanguageToggle() {
  const { language, toggleLanguage } = useLanguage();
  const nextLanguage = language === "en" ? "नेपाली" : "English";
  return (
    <button
      type="button"
      onClick={toggleLanguage}
      className="language-toggle inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl border border-border bg-surface px-3 text-[11px] font-bold text-secondary hover:border-border-strong hover:bg-elevated hover:text-primary"
      aria-label={language === "en" ? "Switch language to Nepali" : "भाषा अङ्ग्रेजीमा बदल्नुहोस्"}
      title={language === "en" ? "Switch to Nepali" : "अङ्ग्रेजीमा बदल्नुहोस्"}
    >
      <Languages size={16} />
      <span className="sm:hidden">{language === "en" ? "ने" : "EN"}</span>
      <span className="hidden sm:inline">{nextLanguage}</span>
    </button>
  );
}
