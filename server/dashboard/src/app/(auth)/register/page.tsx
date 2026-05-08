"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/use-auth";
import { getErrorMessage } from "@/lib/error-message";
import { isValidEmail } from "@/lib/validators";

export default function RegisterPage() {
  const router = useRouter();
  const { user, isLoading, register } = useAuth();
  const { resolvedTheme } = useTheme();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (process.env.NEXT_PUBLIC_ALLOW_REGISTRATION === "false") {
      router.replace("/login");
      return;
    }
    if (!isLoading && user) {
      router.replace("/dashboard/requests");
    }
  }, [isLoading, user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!name.trim()) {
      setError("Name is required.");
      return;
    }

    if (!isValidEmail(email)) {
      setError("Enter a valid email address.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }

    setSubmitting(true);
    try {
      await register(name.trim(), email, password);
      router.push("/dashboard/requests");
    } catch (err) {
      setError(getErrorMessage(err, "Registration failed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      <div className="flex-1 bg-surface-default-primary flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="flex justify-center mb-2">
            {mounted && (
              <Image
                src={resolvedTheme === "dark" ? "/images/logos/logo-light.png" : "/images/logos/logo-dark.png"}
                alt="Mem0"
                width={41}
                height={41}
              />
            )}
          </div>
          <h1 className="text-2xl font-semibold text-onSurface-default-primary text-center mb-6 font-fustat">
            Create your Mem0 account
          </h1>
          <div className="flex flex-col gap-4 border p-8 border-memBorder-primary rounded-xl">
            {error && (
              <p className="text-sm text-onSurface-danger-primary bg-surface-danger-primary px-3 py-2 rounded">
                {error}
              </p>
            )}
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="register-name">Name</Label>
                <Input
                  id="register-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={255}
                  required
                  autoFocus
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="register-email">Email</Label>
                <Input
                  id="register-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  maxLength={255}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="register-password">Password</Label>
                <Input
                  id="register-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="register-confirm-password">Confirm Password</Label>
                <Input
                  id="register-confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
              </div>
              <Button
                type="submit"
                disabled={submitting || !name.trim() || !isValidEmail(email) || !password || !confirmPassword}
                variant="default"
                size="lg"
                className="w-full"
              >
                {submitting ? "Creating account..." : "Create account"}
              </Button>
            </form>
            <Link
              href="/login"
              className="text-xs text-onSurface-default-tertiary hover:text-onSurface-default-primary underline underline-offset-4"
            >
              Already have an account? <span className="underline underline-offset-4 font-medium">Sign in</span>
            </Link>
          </div>
        </div>
      </div>

      <div className="relative hidden h-screen flex-1 items-center justify-center overflow-hidden bg-gradient-to-b from-[#31275A] to-[#5C49A3] px-10 lg:flex">
        <div className="pointer-events-none absolute inset-0 bg-[url('/images/dither.svg')] bg-bottom bg-no-repeat bg-contain" />
        <div className="relative z-10 flex w-full max-w-[564px] flex-col items-center gap-20 text-center text-white">
          <div className="w-full space-y-5">
            <p className="typo-h3 text-white">
              &quot;Mem0 allowed us to unlock true personalized tutoring for
              every student, and it took us just a weekend to integrate.&quot;
            </p>
            <div className="flex flex-col items-center gap-[7px]">
              <div className="flex flex-col items-center gap-1">
                <p className="typo-body-sm text-white">Michael Tong</p>
                <p className="typo-body-xs text-white">CTO, RevisionDojo</p>
              </div>
              <Image
                src="/images/micheal.png"
                alt="Michael Tong"
                width={32}
                height={32}
                className="size-8 rounded-full object-cover"
              />
            </div>
          </div>
          <div className="flex w-full flex-col items-center gap-3">
            <p className="typo-body text-white">Trusted by 100k+ Developers</p>
            <div className="flex items-center justify-center gap-8 text-white">
              <div className="h-6 shrink-0">
                <Image
                  src="/images/logos/aws.svg"
                  alt="AWS"
                  width={41}
                  height={24}
                  className="size-full object-contain"
                />
              </div>
              <div className="h-5 shrink-0">
                <Image
                  src="/images/logos/nvidia.svg"
                  alt="NVIDIA"
                  width={109}
                  height={21}
                  className="size-full object-contain"
                />
              </div>
              <div className="h-[21px] shrink-0">
                <Image
                  src="/images/vercel.png"
                  alt="Vercel"
                  width={66}
                  height={21}
                  className="size-full object-contain"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
