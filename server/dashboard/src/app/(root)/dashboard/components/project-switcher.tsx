"use client";

import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { ChevronDown, FolderKanban, Plus, User } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useProjects } from "@/hooks/use-projects";
import { setActiveProject } from "@/store/reducers/projectReducer";
import { api } from "@/utils/api";
import { PROJECT_ENDPOINTS } from "@/utils/api-endpoints";
import type { RootState } from "@/store/store";
import type { Project } from "@/types/project";

export function ProjectSwitcher() {
  const dispatch = useDispatch();
  const activeProjectId = useSelector(
    (state: RootState) => state.project.activeProjectId,
  );
  const { projects, isLoading, refetch } = useProjects();

  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  const activeProject = projects.find(
    (p: Project) => p.id === activeProjectId,
  );

  // Auto-select first project if none is active
  useEffect(() => {
    if (!activeProjectId && projects.length > 0) {
      const personal = projects.find((p: Project) => p.is_personal);
      dispatch(setActiveProject((personal ?? projects[0]).id));
    }
  }, [activeProjectId, projects, dispatch]);

  const handleSelect = (projectId: string) => {
    dispatch(setActiveProject(projectId));
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await api.post(PROJECT_ENDPOINTS.BASE, { name: newName.trim() });
      await refetch();
      setNewName("");
      setCreateOpen(false);
    } finally {
      setCreating(false);
    }
  };

  const handleDialogClose = (open: boolean) => {
    setCreateOpen(open);
    if (!open) {
      setNewName("");
    }
  };

  if (isLoading) {
    return (
      <div className="w-full px-1.5 py-1.5">
        <div className="h-7 w-full animate-pulse rounded-md bg-surface-default-tertiary" />
      </div>
    );
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            data-testid="project-switcher"
            className="flex items-center gap-2 w-full text-left hover:bg-surface-default-secondary-hover rounded-md p-1.5 transition-colors"
          >
            <div className="flex items-center justify-center size-7 rounded-md bg-surface-default-tertiary shrink-0">
              {activeProject?.is_personal
                ? <User className="size-4 text-onSurface-default-secondary" />
                : <FolderKanban className="size-4 text-onSurface-default-secondary" />}
            </div>
            <span className="typo-body-xs text-onSurface-default-primary truncate flex-1 min-w-0">
              {activeProject?.name ?? "Select Project"}
            </span>
            <ChevronDown className="size-3 text-onSurface-default-tertiary shrink-0" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="start"
          side="bottom"
          className="w-56 font-fustat bg-surface-default-primary border-memBorder-secondary"
        >
          {projects.length === 0 ? (
            <div className="px-2 py-3 text-center">
              <p className="typo-body-xs text-onSurface-default-tertiary">
                No projects yet
              </p>
            </div>
          ) : (
            projects.map((project: Project) => (
              <DropdownMenuItem
                key={project.id}
                onClick={() => handleSelect(project.id)}
                className="typo-body-sm text-onSurface-default-primary hover:bg-surface-default-tertiary-hover focus:bg-surface-default-tertiary-hover cursor-pointer flex items-start justify-between"
              >
                <span className="flex items-start gap-1.5 min-w-0 flex-1">
                  <span className="mt-0.5 shrink-0">
                    {project.is_personal
                      ? <User className="size-3.5 text-onSurface-default-secondary" />
                      : <FolderKanban className="size-3.5 text-onSurface-default-secondary" />}
                  </span>
                  <span className="flex flex-col min-w-0">
                    <span className="truncate">{project.name}</span>
                    {project.description && (
                      <span className="truncate typo-caption-sm text-onSurface-default-tertiary">
                        {project.description}
                      </span>
                    )}
                  </span>
                </span>
                <div className="flex items-center gap-1 shrink-0 ml-2">
                  <Badge
                    variant="outline"
                    className="text-onSurface-default-tertiary border-memBorder-primary typo-caption-sm px-1.5 py-0 capitalize"
                  >
                    {project.role}
                  </Badge>
                  {project.id === activeProjectId && (
                    <Badge
                      variant="outline"
                      className="text-onSurface-default-tertiary border-memBorder-primary typo-caption-sm px-1.5 py-0"
                    >
                      Active
                    </Badge>
                  )}
                </div>
              </DropdownMenuItem>
            ))
          )}
          <DropdownMenuSeparator className="bg-memBorder-primary" />
          <DropdownMenuItem
            onClick={() => setCreateOpen(true)}
            className="typo-body-sm text-onSurface-default-primary hover:bg-surface-default-tertiary-hover focus:bg-surface-default-tertiary-hover cursor-pointer"
          >
            <Plus className="size-4 mr-2" />
            Create Project
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={createOpen} onOpenChange={handleDialogClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Project</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="space-y-2">
              <Label htmlFor="project-name">Project Name</Label>
              <Input
                id="project-name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. My App"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreate();
                }}
              />
            </div>
            <Button
              onClick={handleCreate}
              disabled={!newName.trim() || creating}
              className="w-full"
            >
              {creating ? "Creating..." : "Create"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
