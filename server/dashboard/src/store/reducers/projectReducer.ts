import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { Project } from "@/types/project";

export interface ProjectState {
  activeProjectId: string | null;
  projects: Project[];
}

const getInitialActiveProjectId = (): string | null => {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage.getItem("activeProjectId");
};

const initialState: ProjectState = {
  activeProjectId: getInitialActiveProjectId(),
  projects: [],
};

const projectSlice = createSlice({
  name: "project",
  initialState,
  reducers: {
    setActiveProject(state, action: PayloadAction<string | null>) {
      state.activeProjectId = action.payload;

      if (typeof window !== "undefined") {
        if (action.payload) {
          window.localStorage.setItem("activeProjectId", action.payload);
        } else {
          window.localStorage.removeItem("activeProjectId");
        }
      }
    },
    setProjects(state, action: PayloadAction<Project[]>) {
      state.projects = action.payload;
    },
  },
});

export const { setActiveProject, setProjects } = projectSlice.actions;
export default projectSlice.reducer;
