// Translation interface
interface Translations {
  [key: string]: any;
}

// Load translations from backend
const loadTranslations = async (lang: string): Promise<Translations> => {
  try {
    const response = await fetch(`/translations/${lang}.json`);
    if (!response.ok) {
      throw new Error(`Failed to load translations for ${lang}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Failed to load translations:', error);
    // Fallback to Korean
    if (lang !== 'ko') {
      return loadTranslations('ko');
    }
    return {};
  }
};

// Translation function
export const t = (key: string, lang: string = 'ko', translations: Translations): string => {
  const keys = key.split('.');
  let value: any = translations;
  
  try {
    for (const k of keys) {
      value = value[k];
    }
    return value || key;
  } catch (error) {
    console.warn(`Translation key not found: ${key}`);
    return key;
  }
};

// Get current language from cookie
export const getCurrentLanguage = (): string => {
  const cookies = document.cookie.split(';');
  const languageCookie = cookies.find(cookie => cookie.trim().startsWith('language='));
  
  if (languageCookie) {
    return languageCookie.split('=')[1];
  }
  
  return 'ko'; // Default to Korean
};

// Set language
export const setLanguage = (lang: string): void => {
  document.cookie = `language=${lang}; path=/; max-age=${60 * 60 * 24 * 365}`;
};

// Available languages
export const availableLanguages = ['ko', 'en'];

export { loadTranslations };
