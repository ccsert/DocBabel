import { useContext } from 'react';
import { AuthContext } from './auth-context';

export function useAuth() {
  return useContext(AuthContext);
}