import { createContext, useContext } from 'react';

// Define the user profile structure
interface UserProfile {
  id: string;
}

// Define the context interface
interface UserContextType {
  userProfile: UserProfile | null;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export const useUserContext = (): UserContextType => {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error('useUserContext must be used within a UserProvider');
  }
  return context;
};

export { UserContext };
export type { UserContextType, UserProfile };
