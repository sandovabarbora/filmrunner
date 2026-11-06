/**
 * Hash routes for the editor (no router library, ADR-001):
 *   #/                        productions
 *   #/p/<productionId>        days and crew of one production
 *   #/p/<productionId>/day/new
 *   #/p/<productionId>/day/<callSheetId>
 */

import { useEffect, useState } from "react";

export type Route =
  | { screen: "productions" }
  | { screen: "test" }
  | { screen: "production"; productionId: string; tab: "days" | "crew" | "cast" | "locations" | "members" | "settings" }
  | { screen: "day"; productionId: string; callSheetId: string | null };

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "test") return { screen: "test" };
  if (parts[0] === "p" && parts[1]) {
    if (parts[2] === "day") return { screen: "day", productionId: parts[1], callSheetId: parts[3] && parts[3] !== "new" ? parts[3] : null };
    const tab = parts[2] === "crew" ? "crew" : parts[2] === "cast" ? "cast" : parts[2] === "locations" ? "locations" : parts[2] === "members" ? "members" : parts[2] === "settings" ? "settings" : "days";
    return { screen: "production", productionId: parts[1], tab };
  }
  return { screen: "productions" };
}

export function href(route: Route): string {
  switch (route.screen) {
    case "test": return "#/test";
    case "productions": return "#/";
    case "production": return `#/p/${route.productionId}${route.tab === "days" ? "" : `/${route.tab}`}`;
    case "day": return `#/p/${route.productionId}/day/${route.callSheetId ?? "new"}`;
  }
}

export function navigate(route: Route): void {
  window.location.hash = href(route);
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
