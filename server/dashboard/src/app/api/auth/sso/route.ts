import { cookies, headers } from "next/headers";
import { NextResponse } from "next/server";
import { AUTH_ENDPOINTS } from "@/utils/api-endpoints";
import { getServerApiUrl } from "@/lib/server-api-url";
import {
  REFRESH_COOKIE_NAME,
  REFRESH_COOKIE_OPTIONS,
} from "@/lib/refresh-cookie";

/**
 * Exchanges the Netcetera SSO (Keycloak) access token — injected into the
 * Authorization header by the Envoy Gateway SecurityPolicy in front of this
 * route — for a mem0 session. Only reachable through that gated route, so an
 * absent header just means SSO isn't in front of this deployment.
 */
export async function POST() {
  const headerStore = await headers();
  const authHeader = headerStore.get("authorization");

  if (!authHeader) {
    return NextResponse.json({ error: "No SSO token" }, { status: 401 });
  }

  const res = await fetch(`${getServerApiUrl()}${AUTH_ENDPOINTS.SSO_LOGIN}`, {
    method: "POST",
    headers: { Authorization: authHeader },
  });

  if (!res.ok) {
    return NextResponse.json({ error: "SSO login failed" }, { status: 401 });
  }

  const data = await res.json();
  const cookieStore = await cookies();
  cookieStore.set(
    REFRESH_COOKIE_NAME,
    data.refresh_token,
    REFRESH_COOKIE_OPTIONS,
  );

  return NextResponse.json({ access_token: data.access_token });
}
