export interface Organization {
  id: string;
  name: string;
  created_at: string;
}

export interface Project {
  id: string;
  org_id: string;
  name: string;
  description: string | null;
  collection_name: string;
  is_personal: boolean;
  role: ProjectRole;
  created_at: string;
  updated_at: string;
}

export type ProjectRole = "owner" | "writer" | "reader";

export interface ProjectMember {
  id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  role: ProjectRole;
  created_at: string;
}
