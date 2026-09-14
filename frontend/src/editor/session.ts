/**
 * Who the AD is. Two sources, in this order:
 *  1. a service connection injected into localStorage (tests and tools; no UI),
 *  2. a Supabase Auth session (email code or magic link), the product path.
 * Both resolve to the same Connection the API client uses.
 */

import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import { loadConnection, type Connection } from "./api";

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "https://filmrunner-api.fly.dev";
const SUPABASE_URL: string | undefined = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY: string | undefined = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const signInConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

let client: SupabaseClient | null = null;
export function supabase(): SupabaseClient {
  if (!client) {
    if (!SUPABASE_URL || !SUPABASE_ANON_KEY) throw new Error("Sign-in is not configured for this build");
    // PKCE keeps tokens out of the URL hash, which the editor uses for routing.
    client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, { auth: { flowType: "pkce", persistSession: true, autoRefreshToken: true } });
  }
  return client;
}

export function connectionFromSession(session: Session): Connection {
  return { apiBase: API_BASE, token: session.access_token };
}

export function serviceConnection(): Connection | null {
  return loadConnection();
}

export async function requestCode(email: string): Promise<void> {
  const redirect = window.location.href.split("#")[0];
  const { error } = await supabase().auth.signInWithOtp({ email, options: { emailRedirectTo: redirect, shouldCreateUser: true } });
  if (error) throw error;
}

export async function verifyCode(email: string, code: string): Promise<Session> {
  const { data, error } = await supabase().auth.verifyOtp({ email, token: code.trim(), type: "email" });
  if (error) throw error;
  if (!data.session) throw new Error("No session returned");
  return data.session;
}

export async function signOut(): Promise<void> {
  if (client) await client.auth.signOut();
}
