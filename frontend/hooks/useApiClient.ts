"use client";

import { ApiClient, apiClient } from "@/lib/api-client";

/**
 * Returns the singleton ApiClient instance.
 * Simple accessor hook for consistent access across components.
 */
export function useApiClient(): ApiClient {
  return apiClient;
}
