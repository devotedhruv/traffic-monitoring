import { createContext, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from "react";
import { neTranslations } from "./neTranslations";
import { PRODUCT_NAME } from "../lib/brand";

export type AppLanguage = "en" | "ne";

interface LanguageContextValue {
  language: AppLanguage;
  locale: "en-US" | "ne-NP";
  setLanguage: (language: AppLanguage) => void;
  toggleLanguage: () => void;
  t: (english: string) => string;
}

const STORAGE_KEY = "trafficops-language";
const SETTINGS_KEY = "trafficops-settings-v1";
const LanguageContext = createContext<LanguageContextValue | null>(null);
const textSources = new WeakMap<Text, { source: string; translated: string }>();
const attributeSources = new WeakMap<Element, Map<string, { source: string; translated: string }>>();
const translatedAttributes = ["aria-label", "placeholder", "title", "alt"] as const;

function initialLanguage(): AppLanguage {
  const direct = window.localStorage.getItem(STORAGE_KEY);
  if (direct === "en" || direct === "ne") return direct;
  try {
    const stored = JSON.parse(window.localStorage.getItem(SETTINGS_KEY) ?? "null") as { general?: { language?: string } } | null;
    return stored?.general?.language === "ne" ? "ne" : "en";
  } catch {
    return "en";
  }
}

function translateDynamic(value: string) {
  const patterns: Array<[RegExp, (...matches: string[]) => string]> = [
    [/^Step (\d+) of (\d+)$/, (_all, step, total) => `${total} मध्ये चरण ${step}`],
    [/^(\d+) results$/, (_all, count) => `${count} नतिजा`],
    [/^(\d+) alerts$/, (_all, count) => `${count} अलर्ट`],
    [/^Page (\d+) of (\d+)$/, (_all, page, total) => `${total} मध्ये पृष्ठ ${page}`],
    [/^Signed in as (.+)$/, (_all, name) => `${name} को रूपमा साइन इन गरिएको`],
    [/^Continue to SadakDrishti as (.+)\.$/, (_all, email) => `${email} को रूपमा SadakDrishti जारी राख्नुहोस्।`],
    [/^Delete (.+)$/, (_all, item) => `${item} मेटाउनुहोस्`],
    [/^Counting-line position · (.+)$/, (_all, position) => `गणना रेखाको स्थान · ${position}`],
    [/^(\d+) detections$/, (_all, count) => `${count} पहिचान`],
    [/^(\d+(?:\.\d+)?)% of total$/, (_all, percent) => `कुलको ${percent}%`]
  ];
  for (const [pattern, replacement] of patterns) {
    const match = value.match(pattern);
    if (match) return replacement(...match);
  }
  return value;
}

function translateToNepali(english: string) {
  const leading = english.match(/^\s*/)?.[0] ?? "";
  const trailing = english.match(/\s*$/)?.[0] ?? "";
  const value = english.trim();
  if (!value) return english;
  const translated = neTranslations[value] ?? translateDynamic(value);
  return translated === value ? english : `${leading}${translated}${trailing}`;
}

function localizeText(node: Text, language: AppLanguage) {
  const current = node.data;
  const previous = textSources.get(node);
  if (language === "en") {
    if (previous) {
      if (current !== previous.source) node.data = previous.source;
      textSources.delete(node);
    }
    return;
  }

  let source = previous?.source ?? current;
  if (previous && current !== previous.source && current !== previous.translated) source = current;
  const translated = translateToNepali(source);
  if (translated === source) return;
  textSources.set(node, { source, translated });
  if (current !== translated) node.data = translated;
}

function localizeAttribute(element: Element, attribute: string, language: AppLanguage) {
  const current = element.getAttribute(attribute);
  if (current === null) return;
  const records = attributeSources.get(element) ?? new Map<string, { source: string; translated: string }>();
  const previous = records.get(attribute);
  if (language === "en") {
    if (previous) {
      if (current !== previous.source) element.setAttribute(attribute, previous.source);
      records.delete(attribute);
    }
    return;
  }

  let source = previous?.source ?? current;
  if (previous && current !== previous.source && current !== previous.translated) source = current;
  const translated = translateToNepali(source);
  if (translated === source) return;
  records.set(attribute, { source, translated });
  attributeSources.set(element, records);
  if (current !== translated) element.setAttribute(attribute, translated);
}

function localizeNode(root: Node, language: AppLanguage) {
  if (root instanceof Text) {
    if (!root.parentElement?.closest("script, style")) localizeText(root, language);
    return;
  }
  if (!(root instanceof Element || root instanceof Document)) return;
  const owner = root instanceof Document ? root.documentElement : root;
  if (owner.matches?.("script, style")) return;

  const walker = document.createTreeWalker(owner, NodeFilter.SHOW_TEXT);
  let text = walker.nextNode();
  while (text) {
    if (!text.parentElement?.closest("script, style")) localizeText(text as Text, language);
    text = walker.nextNode();
  }

  const elements = [owner, ...Array.from(owner.querySelectorAll("[aria-label], [placeholder], [title], [alt]"))];
  for (const element of elements) {
    for (const attribute of translatedAttributes) localizeAttribute(element, attribute, language);
  }
}

function persistLanguage(language: AppLanguage) {
  window.localStorage.setItem(STORAGE_KEY, language);
  try {
    const raw = window.localStorage.getItem(SETTINGS_KEY);
    if (!raw) return;
    const settings = JSON.parse(raw) as { general?: { language?: string } };
    if (settings.general) {
      settings.general.language = language;
      window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    }
  } catch {
    // A malformed settings record is handled by the existing settings loader.
  }
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<AppLanguage>(initialLanguage);

  useLayoutEffect(() => {
    document.documentElement.lang = language === "ne" ? "ne" : "en";
    document.documentElement.dataset.language = language;
    document.title = language === "ne" ? `${PRODUCT_NAME} — ट्राफिक निगरानी` : PRODUCT_NAME;
    localizeNode(document, language);

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === "characterData") localizeNode(mutation.target, language);
        else if (mutation.type === "attributes") localizeAttribute(mutation.target as Element, mutation.attributeName ?? "", language);
        else mutation.addedNodes.forEach((node) => localizeNode(node, language));
      }
    });
    observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: [...translatedAttributes] });
    return () => observer.disconnect();
  }, [language]);

  const setLanguage = (next: AppLanguage) => {
    persistLanguage(next);
    setLanguageState(next);
  };
  const value = useMemo<LanguageContextValue>(() => ({
    language,
    locale: language === "ne" ? "ne-NP" : "en-US",
    setLanguage,
    toggleLanguage: () => setLanguage(language === "en" ? "ne" : "en"),
    t: (english) => language === "ne" ? translateToNepali(english) : english
  }), [language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useLanguage() {
  const value = useContext(LanguageContext);
  if (!value) throw new Error("useLanguage must be used within LanguageProvider");
  return value;
}
