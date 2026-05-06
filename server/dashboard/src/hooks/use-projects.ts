"use client";

import { useApiQuery } from "@/hooks/use-api-query";
import { api } from "@/utils/api";
import { PROJECT_ENDPOINTS } from "@/utils/api-endpoints";
import type { Project, ProjectMember } from "@/types/project";

export function useProjects() {
  const { data, isLoading, error, refetch } = useApiQuery<Project[]>(
    async () => {
      const response = await api.get(PROJECT_ENDPOINTS.BASE);
      return response.data;
    },
    { initialData: [] },
  );

  return {
    projects: data ?? [],
    isLoading,
    error,
    refetch,
  };
}

export function useProjectMembers(projectId: string | null) {
  const { data, isLoading, error, refetch } = useApiQuery<ProjectMember[]>(
    async () => {
      if (!projectId) {
        return [];
      }

      const response = await api.get(PROJECT_ENDPOINTS.MEMBERS(projectId));
      return response.data;
    },
    {
      enabled: Boolean(projectId),
      initialData: [],
    },
  );

  return {
    members: data ?? [],
    isLoading,
    error,
    refetch,
  };
}
