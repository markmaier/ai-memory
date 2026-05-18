"use client";

import { useState } from "react";
import { useApiQuery } from "@/hooks/use-api-query";
import { api } from "@/utils/api";
import { USER_ENDPOINTS } from "@/utils/api-endpoints";
import { useAuth } from "@/hooks/use-auth";
import { DataTable } from "@/components/shared/data-table";
import { TableSkeleton } from "@/components/shared/table-skeleton";
import { EmptyState } from "@/components/self-hosted/empty-state";
import DeleteConfirmationModal from "@/components/ui/delete-confirmation-modal";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/use-toast";
import { getErrorMessage } from "@/lib/error-message";
import { Trash2 } from "lucide-react";
import { format } from "date-fns";

interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at: string;
}

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const [userToDelete, setUserToDelete] = useState<AdminUser | null>(null);

  const {
    data: users,
    isLoading,
    refetch,
  } = useApiQuery<AdminUser[]>(
    async () => {
      const res = await api.get(USER_ENDPOINTS.BASE);
      return res.data;
    },
    { initialData: [] },
  );

  const handleDeleteUser = async () => {
    if (!userToDelete) return;
    try {
      await api.delete(USER_ENDPOINTS.BY_ID(userToDelete.id));
      toast({ title: "User removed", variant: "success" });
      setUserToDelete(null);
      void refetch();
    } catch (error) {
      toast({
        title: "Failed to remove user",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    }
  };

  const columns = [
    {
      key: "name" as keyof AdminUser,
      label: "Name",
      width: 160,
    },
    {
      key: "email" as keyof AdminUser,
      label: "Email",
      width: 220,
    },
    {
      key: "role" as keyof AdminUser,
      label: "Role",
      width: 90,
      render: (value: AdminUser[keyof AdminUser]) => (
        <Badge
          variant="outline"
          className="capitalize text-onSurface-default-tertiary border-memBorder-primary typo-caption-sm px-1.5 py-0"
        >
          {String(value)}
        </Badge>
      ),
    },
    {
      key: "created_at" as keyof AdminUser,
      label: "Joined",
      width: 120,
      render: (value: AdminUser[keyof AdminUser]) =>
        format(new Date(String(value)), "MMM d, yyyy"),
    },
    {
      key: "id" as keyof AdminUser,
      label: "",
      width: 40,
      render: (_: AdminUser[keyof AdminUser], row: AdminUser) => {
        const isSelf = row.id === currentUser?.id;
        return (
          <Button
            variant="ghost"
            size="icon"
            disabled={isSelf}
            onClick={() => setUserToDelete(row)}
            className="size-7"
            title={isSelf ? "You cannot delete your own account" : "Remove user"}
          >
            <Trash2 className="size-3.5 text-onSurface-danger-primary" />
          </Button>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold font-fustat">User Management</h1>

      {isLoading ? (
        <TableSkeleton rows={4} columns={4} />
      ) : !users || users.length === 0 ? (
        <EmptyState title="No users" description="No registered users found." />
      ) : (
        <div className="rounded-md border border-memBorder-primary overflow-hidden">
          <DataTable
            data={users}
            columns={columns}
            getRowKey={(row) => row.id}
          />
        </div>
      )}

      <DeleteConfirmationModal
        isOpen={!!userToDelete}
        onClose={() => setUserToDelete(null)}
        onConfirm={handleDeleteUser}
        title="Remove user"
        description="This will permanently delete the user, their personal memories, and remove them from all projects. This cannot be undone."
        itemName={userToDelete?.email ?? ""}
        confirmButtonText="Confirm"
        abortButtonText="Abort"
      />
    </div>
  );
}
