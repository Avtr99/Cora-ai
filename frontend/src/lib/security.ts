/**
 * Security utilities for the VCM application
 * Includes input sanitization and other security helpers
 */

import DOMPurify from 'dompurify';

/**
 * Sanitizes user input to prevent XSS attacks
 * @param input - The user input to sanitize
 * @returns Sanitized string safe for display
 */
export function sanitizeInput(input: string): string {
  if (!input) return '';
  
  // Use DOMPurify to sanitize HTML and prevent XSS
  const sanitized = DOMPurify.sanitize(input, {
    ALLOWED_TAGS: [], // No HTML tags allowed
    ALLOWED_ATTR: [] // No HTML attributes allowed
  });
  
  return sanitized;
}

/**
 * Sanitizes HTML content when some HTML tags need to be preserved
 * Useful for rendering markdown or formatted content
 * @param html - The HTML content to sanitize
 * @returns Sanitized HTML with only allowed tags
 */
export function sanitizeHTML(html: string): string {
  if (!html) return '';
  
  // Use DOMPurify with a limited set of allowed tags
  const sanitized = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'ul', 'ol', 'li', 'br', 'code', 'pre'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
    FORBID_TAGS: ['script', 'style', 'iframe', 'form', 'input'],
    ADD_ATTR: ['target'], // For safe external links
    ADD_URI_SAFE_ATTR: ['href']
  });
  
  return sanitized;
}

/**
 * Validates and sanitizes URL parameters
 * @param url - The URL to validate
 * @returns A sanitized URL or empty string if invalid
 */
const DANGEROUS_PROTOCOLS = new Set([
  'javascript:',
  'data:',
  'vbscript:',
  'file:',
  'about:',
]);

export function sanitizeUrl(url: string): string {
  if (!url) return '';

  try {
    // Check if URL is valid
    const parsedUrl = new URL(url);

    // Block dangerous protocols explicitly; allow only http/https.
    if (DANGEROUS_PROTOCOLS.has(parsedUrl.protocol.toLowerCase())) {
      return '';
    }
    if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
      return '';
    }

    return parsedUrl.toString();
  } catch (error) {
    // Invalid URL
    return '';
  }
}

/**
 * Security helper for content preview
 * @param content - The content to preview
 * @param maxLength - Maximum length to show (default: 100)
 * @returns Truncated and sanitized string
 */
export function safePreview(content: string, maxLength: number = 100): string {
  if (!content) return '';
  
  const sanitized = sanitizeInput(content);
  
  if (sanitized.length <= maxLength) {
    return sanitized;
  }
  
  return `${sanitized.substring(0, maxLength)}...`;
}
