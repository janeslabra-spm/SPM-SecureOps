import axios from "axios";

/**
 * Axios HTTP client configured for the Security Monitoring System backend.
 * All REST API calls should use this instance.
 */
const api = axios.create({
  baseURL: "http://localhost:8000",
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Response interceptor for consistent error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("[API Error]", error.response?.status, error.message);
    return Promise.reject(error);
  }
);

export default api;
