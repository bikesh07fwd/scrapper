/**
 * src/api/queries.js — React Query hooks wrapper.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getHealth,
  getJobs,
  getRuns,
  getJob,
  getRun,
  triggerAdapter,
} from "./client";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 10000, // Poll every 10 seconds
    retry: 2,
    refetchOnWindowFocus: true,
  });
}

export function useJobs(limit = 20, offset = 0) {
  return useQuery({
    queryKey: ["jobs", limit, offset],
    queryFn: () => getJobs(limit, offset),
    refetchInterval: 30000, // Poll every 30 seconds
    keepPreviousData: true,
  });
}

export function useJob(id) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: () => getJob(id),
    enabled: !!id,
  });
}

export function useRuns(limit = 20, offset = 0) {
  return useQuery({
    queryKey: ["runs", limit, offset],
    queryFn: () => getRuns(limit, offset),
    refetchInterval: 10000, // Poll every 10 seconds
    keepPreviousData: true,
  });
}

export function useRun(id) {
  return useQuery({
    queryKey: ["run", id],
    queryFn: () => getRun(id),
    enabled: !!id,
  });
}

export function useTriggerAdapter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ adapter, scenario }) => triggerAdapter(adapter, scenario),
    onSuccess: () => {
      // Invalidate health, jobs, and runs after a manual trigger completes
      queryClient.invalidateQueries({ queryKey: ["health"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}
