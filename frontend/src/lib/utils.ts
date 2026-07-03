import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Generates a short, readable project name from a full case study title.
 * Extracts key location/project identifier for navigation display.
 * 
 * Examples:
 * - "Reforestation And Restoration Of Degraded Mangrove Lands, Sustainable Livelihood And Community Development In Myanmar" 
 *   -> "Mangrove Myanmar"
 * - "Humbo Ethiopia Assisted Natural Regeneration Project" 
 *   -> "Humbo Ethiopia"
 */
export function getShortProjectName(fullTitle: string): string {
  // Remove common project description words
  const cleanedTitle = fullTitle
    .replace(/Project$/i, '')
    .replace(/Assisted Natural Regeneration$/i, '')
    .replace(/Reforestation And Restoration Of Degraded/i, '')
    .replace(/Sustainable Livelihood And Community Development In/i, '')
    .replace(/Lands,?/i, '')
    .trim();
  
  // Extract the first 2-3 meaningful words (typically location + project type)
  const words = cleanedTitle.split(/\s+/).filter(word => word.length > 2 || /^[A-Z]{2}$/.test(word));
  
  if (words.length === 0) return fullTitle;
  if (words.length <= 2) return words.join(' ');
  
  // Take first 2 words for brevity in navigation
  return words.slice(0, 2).join(' ');
}
