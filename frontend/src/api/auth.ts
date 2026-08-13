import { apiClient } from "./client";
import type { MeResponse } from "../types";

export interface RegisterPayload {
  company_name: string;
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

export async function registerAccount(payload: RegisterPayload): Promise<string> {
  const { data } = await apiClient.post<TokenResponse>("/auth/register", payload);
  return data.access_token;
}

export async function login(payload: LoginPayload): Promise<string> {
  const { data } = await apiClient.post<TokenResponse>("/auth/login", payload);
  return data.access_token;
}

export async function fetchMe(): Promise<MeResponse> {
  const { data } = await apiClient.get<MeResponse>("/auth/me");
  return data;
}
