import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { migrateActionUrl } from "@/lib/entity-routing";

// Public paths that don't require authentication
const PUBLIC_PATHS = ["/login", "/setup"];

export function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;

  // Skip API routes, static files, Next.js internals
  if (
    pathname.startsWith("/api/") ||
    pathname.startsWith("/_next/") ||
    pathname.startsWith("/favicon")
  ) {
    return NextResponse.next();
  }

  // The root opens the dealer home: Inventory when signed in, else the login page.
  if (pathname === "/") {
    const target = request.cookies.has("refresh_token") ? "/inventory" : "/login";
    return NextResponse.redirect(new URL(target, request.url));
  }

  // Allow public pages
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Check for refresh_token cookie — lightweight gate.
  // Real auth happens at the FastAPI gateway. This just prevents
  // showing the authenticated UI to users with no session cookie.
  const hasRefreshToken = request.cookies.has("refresh_token");
  if (!hasRefreshToken) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  // Redirect old ?action= URLs to new path-based routes
  // e.g. /skills/propertyclaw?action=list-properties → /skills/propertyclaw/properties
  const skillMatch = pathname.match(/^\/skills\/([^/]+)$/);
  if (skillMatch && searchParams.has("action")) {
    const newPath = migrateActionUrl(pathname, searchParams);
    if (newPath) {
      const url = request.nextUrl.clone();
      url.pathname = newPath.split("?")[0];
      url.search = newPath.includes("?") ? newPath.slice(newPath.indexOf("?")) : "";
      return NextResponse.redirect(url, 308);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
