"use client";

import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Check, ChevronsUpDown, Plus, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { DataTable } from "@/components/shared/data-table";
import { TableSkeleton } from "@/components/shared/table-skeleton";
import { EmptyState } from "@/components/self-hosted/empty-state";
import DeleteConfirmationModal from "@/components/ui/delete-confirmation-modal";
import { api } from "@/utils/api";
import { AUTH_ENDPOINTS, PROJECT_ENDPOINTS } from "@/utils/api-endpoints";
import { toast } from "@/components/ui/use-toast";
import { format } from "date-fns";
import { getErrorMessage } from "@/lib/error-message";
import { useProjectMembers, useProjects } from "@/hooks/use-projects";
import { useAuth } from "@/hooks/use-auth";
import { setActiveProject } from "@/store/reducers/projectReducer";
import type { RootState } from "@/store/store";
import type { ProjectMember, ProjectRole } from "@/types/project";

interface UserSummary {
  id: string;
  name: string;
  email: string;
}

export default function ProjectsPage() {
  const { user } = useAuth();
  const dispatch = useDispatch();
  const activeProjectId = useSelector(
    (state: RootState) => state.project.activeProjectId,
  );
  const { projects, refetch: refetchProjects } = useProjects();

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  const {
    members,
    isLoading: membersLoading,
    refetch: refetchMembers,
  } = useProjectMembers(activeProjectId);

  const currentMember = members.find((m) => m.user_id === user?.id);
  const isOwner = currentMember?.role === "owner";

  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [savingProject, setSavingProject] = useState(false);

  const [addOpen, setAddOpen] = useState(false);
  const [comboOpen, setComboOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserSummary | null>(null);
  const [newRole, setNewRole] = useState<ProjectRole>("reader");
  const [registeredUsers, setRegisteredUsers] = useState<UserSummary[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);

  const [memberToRemove, setMemberToRemove] = useState<ProjectMember | null>(
    null,
  );

  const [deleteProjectOpen, setDeleteProjectOpen] = useState(false);

  useEffect(() => {
    if (activeProject) {
      setProjectName(activeProject.name);
      setProjectDescription(activeProject.description ?? "");
    }
  }, [activeProject]);

  const projectDirty =
    activeProject !== null &&
    (projectName !== activeProject.name ||
      projectDescription !== (activeProject.description ?? ""));
  const projectValid = projectName.trim().length > 0;

  const handleSaveProject = async () => {
    if (!activeProjectId) return;
    setSavingProject(true);
    try {
      await api.patch(PROJECT_ENDPOINTS.BY_ID(activeProjectId), {
        name: projectName.trim(),
        description: projectDescription.trim() || null,
      });
      toast({ title: "Project updated", variant: "success" });
      void refetchProjects();
    } catch (error) {
      toast({
        title: "Failed to update project",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    } finally {
      setSavingProject(false);
    }
  };

  const handleDialogOpenChange = async (open: boolean) => {
    setAddOpen(open);
    if (open && registeredUsers.length === 0) {
      setUsersLoading(true);
      try {
        const response = await api.get(AUTH_ENDPOINTS.USERS);
        setRegisteredUsers(response.data);
      } catch (error) {
        toast({
          title: "Failed to load users",
          description: getErrorMessage(error),
          variant: "destructive",
        });
      } finally {
        setUsersLoading(false);
      }
    }
    if (!open) {
      setSelectedUser(null);
      setNewRole("reader");
      setComboOpen(false);
    }
  };

  const handleAddMember = async () => {
    if (!activeProjectId || !selectedUser) return;
    try {
      await api.post(PROJECT_ENDPOINTS.MEMBERS(activeProjectId), {
        email: selectedUser.email,
        role: newRole,
      });
      toast({ title: "Member added", variant: "success" });
      setAddOpen(false);
      setSelectedUser(null);
      setNewRole("reader");
      void refetchMembers();
    } catch (error) {
      toast({
        title: "Failed to add member",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    }
  };

  const handleChangeRole = async (member: ProjectMember, role: ProjectRole) => {
    if (!activeProjectId) return;
    try {
      await api.patch(
        PROJECT_ENDPOINTS.MEMBER_BY_ID(activeProjectId, member.id),
        { role },
      );
      toast({ title: "Role updated", variant: "success" });
      void refetchMembers();
    } catch (error) {
      toast({
        title: "Failed to update role",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    }
  };

  const handleRemoveMember = async () => {
    if (!activeProjectId || !memberToRemove) return;
    try {
      await api.delete(
        PROJECT_ENDPOINTS.MEMBER_BY_ID(activeProjectId, memberToRemove.id),
      );
      toast({ title: "Member removed", variant: "success" });
      setMemberToRemove(null);
      void refetchMembers();
    } catch (error) {
      toast({
        title: "Failed to remove member",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    }
  };

  const handleDeleteProject = async () => {
    if (!activeProjectId) return;
    try {
      await api.delete(PROJECT_ENDPOINTS.BY_ID(activeProjectId));
      toast({ title: "Project deleted", variant: "success" });
      setDeleteProjectOpen(false);
      const remaining = projects.filter((p) => p.id !== activeProjectId);
      const personal = remaining.find((p) => p.is_personal);
      dispatch(setActiveProject(personal?.id ?? remaining[0]?.id ?? null));
      void refetchProjects();
    } catch (error) {
      toast({
        title: "Failed to delete project",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    }
  };

  const columns = [
    { key: "user_name" as keyof ProjectMember, label: "Name", width: 150 },
    { key: "user_email" as keyof ProjectMember, label: "Email", width: 200 },
    {
      key: "role" as keyof ProjectMember,
      label: "Role",
      width: 120,
      render: (value: ProjectMember[keyof ProjectMember], row: ProjectMember) =>
        isOwner ? (
          <Select
            value={row.role}
            onValueChange={(v) => handleChangeRole(row, v as ProjectRole)}
          >
            <SelectTrigger className="h-7 w-24 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="owner">Owner</SelectItem>
              <SelectItem value="writer">Writer</SelectItem>
              <SelectItem value="reader">Reader</SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <span className="text-sm capitalize">{String(value)}</span>
        ),
    },
    {
      key: "created_at" as keyof ProjectMember,
      label: "Joined",
      width: 120,
      render: (value: ProjectMember[keyof ProjectMember]) =>
        format(new Date(String(value)), "MMM d, yyyy"),
    },
    ...(isOwner
      ? [
          {
            key: "id" as keyof ProjectMember,
            label: "",
            width: 40,
            render: (
              _: ProjectMember[keyof ProjectMember],
              row: ProjectMember,
            ) => (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setMemberToRemove(row)}
                className="size-7"
              >
                <Trash2 className="size-3.5 text-onSurface-danger-primary" />
              </Button>
            ),
          },
        ]
      : []),
  ];

  if (!activeProject) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold font-fustat">Project Settings</h1>
        <EmptyState
          title="No project selected"
          description="Select a project from the sidebar to manage its settings and members."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold font-fustat">Project Settings</h1>

      <Card className="border-memBorder-primary">
        <CardHeader>
          <CardTitle className="text-sm">Project Info</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="project-name" className="text-xs">
                Name
              </Label>
              {isOwner ? (
                <Input
                  id="project-name"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                />
              ) : (
                <p className="text-sm py-2">{activeProject.name}</p>
              )}
            </div>
            <div className="space-y-1">
              <Label htmlFor="project-description" className="text-xs">
                Description
              </Label>
              {isOwner ? (
                <Input
                  id="project-description"
                  value={projectDescription}
                  onChange={(e) => setProjectDescription(e.target.value)}
                  placeholder="Optional description"
                />
              ) : (
                <p className="text-sm py-2 text-onSurface-default-secondary">
                  {activeProject.description || "No description"}
                </p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Collection</Label>
              <p className="text-sm py-2 font-mono text-onSurface-default-secondary">
                {activeProject.collection_name}
              </p>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Created</Label>
              <p className="text-sm py-2 text-onSurface-default-secondary">
                {format(new Date(activeProject.created_at), "MMM d, yyyy")}
              </p>
            </div>
          </div>
          {isOwner && (
            <Button
              onClick={handleSaveProject}
              disabled={!projectDirty || !projectValid || savingProject}
            >
              {savingProject ? "Saving..." : "Save changes"}
            </Button>
          )}
          {isOwner && !activeProject.is_personal && (
            <Button
              variant="destructive"
              onClick={() => setDeleteProjectOpen(true)}
            >
              Delete Project
            </Button>
          )}
        </CardContent>
      </Card>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold font-fustat">Members</h2>
          {isOwner && !activeProject.is_personal && (
            <Dialog open={addOpen} onOpenChange={handleDialogOpenChange}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="size-4 mr-1" /> Add Member
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add Member</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 mt-2">
                  <div className="space-y-2">
                    <Label>User</Label>
                    <Popover open={comboOpen} onOpenChange={setComboOpen}>
                      <PopoverTrigger asChild>
                        <Button
                          variant="outline"
                          role="combobox"
                          aria-expanded={comboOpen}
                          className="w-full justify-between font-normal"
                          disabled={usersLoading}
                        >
                          {usersLoading
                            ? "Loading users…"
                            : selectedUser
                              ? `${selectedUser.name} · ${selectedUser.email}`
                              : "Select a user…"}
                          <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-full p-0" align="start">
                        <Command>
                          <CommandInput placeholder="Search by name or email…" />
                          <CommandList>
                            <CommandEmpty>No matching users.</CommandEmpty>
                            <CommandGroup>
                              {registeredUsers
                                .filter(
                                  (u) =>
                                    !members.some((m) => m.user_id === u.id),
                                )
                                .map((u) => (
                                  <CommandItem
                                    key={u.id}
                                    value={`${u.name} ${u.email}`}
                                    onSelect={() => {
                                      setSelectedUser(u);
                                      setComboOpen(false);
                                    }}
                                  >
                                    <Check
                                      className={cn(
                                        "mr-2 size-4",
                                        selectedUser?.id === u.id
                                          ? "opacity-100"
                                          : "opacity-0",
                                      )}
                                    />
                                    <span>
                                      {u.name}
                                      <span className="text-muted-foreground">
                                        {" · "}{u.email}
                                      </span>
                                    </span>
                                  </CommandItem>
                                ))}
                            </CommandGroup>
                          </CommandList>
                        </Command>
                      </PopoverContent>
                    </Popover>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="member-role">Role</Label>
                    <Select
                      value={newRole}
                      onValueChange={(v) => setNewRole(v as ProjectRole)}
                    >
                      <SelectTrigger id="member-role">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="owner">Owner</SelectItem>
                        <SelectItem value="writer">Writer</SelectItem>
                        <SelectItem value="reader">Reader</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button
                    onClick={handleAddMember}
                    disabled={!selectedUser}
                    className="w-full"
                  >
                    Add
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          )}
        </div>

        {membersLoading ? (
          <TableSkeleton rows={3} columns={4} />
        ) : members.length === 0 ? (
          <EmptyState
            title="No members"
            description="This project has no members yet."
          />
        ) : (
          <Card className="border-memBorder-primary overflow-hidden">
            <DataTable
              data={members}
              columns={columns}
              getRowKey={(row) => row.id}
            />
          </Card>
        )}
      </div>

      <DeleteConfirmationModal
        isOpen={!!memberToRemove}
        onClose={() => setMemberToRemove(null)}
        onConfirm={handleRemoveMember}
        title="Remove member"
        description="This member will lose access to the project immediately. This cannot be undone."
        itemName={memberToRemove?.user_email ?? ""}
        confirmButtonText="Remove"
      />

      <DeleteConfirmationModal
        isOpen={deleteProjectOpen}
        onClose={() => setDeleteProjectOpen(false)}
        onConfirm={handleDeleteProject}
        title="Delete project"
        description="This will permanently delete the project and all its memories. This action cannot be undone."
        itemName={activeProject.name}
        confirmButtonText="Confirm"
        abortButtonText="Abort"
      />
    </div>
  );
}
