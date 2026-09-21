import axios from 'axios';
import { useAuthStore } from '../store/authStore';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:4000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach the JWT to every outgoing request
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Access tokens are short-lived. On a 401 we try ONE silent refresh with the
// stored refresh token and replay the request; only if that fails does the
// session end and the UI fall back to the login screen. Concurrent 401s share a
// single in-flight refresh — refresh tokens are single-use, so two parallel
// refreshes with the same token would otherwise race.
let refreshInFlight: Promise<string | null> | null = null;

function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  const { refreshToken } = useAuthStore.getState();
  if (!refreshToken) return Promise.resolve(null);

  refreshInFlight = axios
    .post(`${API_BASE_URL}/api/auth/refresh`, { refresh_token: refreshToken })
    .then(({ data }) => {
      useAuthStore.getState().setTokens(data.token, data.refresh_token);
      return data.token as string;
    })
    .catch(async (err) => {
      // Another tab may have rotated the token a moment ago — its result is in
      // localStorage. Pick it up and treat that as success before giving up.
      await useAuthStore.persist.rehydrate();
      const latest = useAuthStore.getState();
      if (latest.refreshToken && latest.refreshToken !== refreshToken && latest.token) return latest.token;
      // Only a definite "no" from the server ends the session; a network blip
      // must not sign someone out.
      if (axios.isAxiosError(err) && err.response?.status === 401) return null;
      throw err;
    })
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

// The backend's shared auth dependency (core/deps.py) answers a dead/expired
// access token with exactly this message. Other 401s — wrong password on a
// "confirm your password" form, a bad 2FA code — are ordinary errors for the
// calling screen to show, and must not sign anyone out.
const SESSION_EXPIRED_DETAIL = 'Invalid or expired token';

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as (typeof error.config & { _retried?: boolean }) | undefined;
    const isSessionExpiry =
      error.response?.status === 401 &&
      error.response?.data?.detail === SESSION_EXPIRED_DETAIL &&
      Boolean(original?.headers?.Authorization);

    if (!isSessionExpiry || !original) return Promise.reject(error);

    if (!original._retried) {
      original._retried = true;
      try {
        const newToken = await refreshAccessToken();
        if (newToken) {
          original.headers.Authorization = `Bearer ${newToken}`;
          return apiClient(original);
        }
      } catch {
        // Network trouble while refreshing: fail this request, keep the session.
        return Promise.reject(error);
      }
    }
    // No refresh token (a session from before refresh tokens existed), the
    // server refused it, or a fresh token was rejected too: the session is over.
    useAuthStore.getState().logout();
    return Promise.reject(error);
  }
);

// Extracts a human-readable error message from any error thrown during
// an API call (axios errors, native errors, or unknown values).
export function getErrorMessage(error: unknown, fallback = 'An unexpected error occurred'): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    return (
      (typeof detail === 'string' ? detail : undefined) ||
      error.response?.data?.message ||
      error.response?.data?.error ||
      error.message ||
      fallback
    );
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
}