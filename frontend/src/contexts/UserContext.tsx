import { useState, useEffect, ReactNode } from 'react';
import { UserContext } from './useUserContext';
import type { UserProfile } from './useUserContext';

interface UserProviderProps {
  children: ReactNode;
}

function generateUserId(): string {
  return 'user_' + Math.random().toString(36).substring(2, 15);
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
