import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** R1-4: hide /dev/* debug surfaces in production builds. */
export function middleware(request: NextRequest) {
  if (process.env.NODE_ENV !== "production") {
    return NextResponse.next();
  }
  const path = request.nextUrl.pathname;
  if (path === "/dev" || path.startsWith("/dev/")) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dev", "/dev/:path*"],
};
