import { useState, useEffect, ReactNode } from 'react';
import { UserContext } from './useUserContext';
import type { UserProfile } from './useUserContext';

interface UserProviderProps {
  children: ReactNode;
}

function generateUserId(): string {
  // Use the Web Crypto API for a cryptographically secure random UUID when
  // available. Fall back to getRandomValues for older browsers. Math.random()
  // is intentionally avoided because the user ID is used as an identifier in
  // feedback and memory API calls.
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return 'user_' + crypto.randomUUID();
  }
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
    return 'user_' + hex;
  }
  // Last-resort fallback for extremely old environments without Web Crypto.
  return 'user_' + Date.now().toString(36) + Math.random().toString(36).substring(2, 10);
}

export function UserProvider({ children }: UserProviderProps): JSX.Element {
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);

  // Load user profile from localStorage on mount
  useEffect(() => {
    const loadUserProfile = () => {
      try {
        const storedProfile = localStorage.getItem('userProfile');

        if (storedProfile) {
          const parsedProfile = JSON.parse(storedProfile) as UserProfile;
          setUserProfile(parsedProfile);
        } else {
          // Create a new user profile if none exists
          const newProfile: UserProfile = {
            id: generateUserId(),
          };

          localStorage.setItem('userProfile', JSON.stringify(newProfile));
          setUserProfile(newProfile);
        }
      } catch {
        // Private browsing or disabled localStorage: generate a transient user.
        setUserProfile({ id: generateUserId() });
      }
    };

    loadUserProfile();
  }, []);

  // Save user profile to localStorage whenever it changes
  useEffect(() => {
    if (userProfile) {
      try {
        localStorage.setItem('userProfile', JSON.stringify(userProfile));
      } catch {
        // Ignore localStorage write failures (e.g. private browsing).
      }
    }
  }, [userProfile]);

  return (
    <UserContext.Provider value={{ userProfile }}>
      {children}
    </UserContext.Provider>
  );
}
